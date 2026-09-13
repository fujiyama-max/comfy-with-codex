#!/usr/bin/env python3
"""Submit an API-format ComfyUI workflow and download its image outputs."""

from __future__ import annotations

import argparse
import json
import shutil
import sys
import time
import uuid
from pathlib import Path
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import Request, urlopen


def request_json(url: str, *, method: str = "GET", payload: Any | None = None) -> dict[str, Any]:
    body = None if payload is None else json.dumps(payload).encode("utf-8")
    request = Request(url, data=body, method=method)
    if body is not None:
        request.add_header("Content-Type", "application/json")
    try:
        with urlopen(request, timeout=30) as response:
            return json.load(response)
    except HTTPError as error:
        detail = error.read().decode("utf-8", errors="replace")
        raise RuntimeError(f"ComfyUI returned HTTP {error.code}: {detail}") from error
    except URLError as error:
        raise RuntimeError(f"Cannot reach ComfyUI at {url}: {error.reason}") from error


def set_input(workflow: dict[str, Any], node_id: str | None, input_name: str, value: Any) -> None:
    if node_id is None:
        return
    try:
        inputs = workflow[str(node_id)]["inputs"]
    except KeyError as error:
        raise ValueError(f"Node {node_id!r} is not present in the workflow.") from error
    if input_name not in inputs:
        raise ValueError(f"Node {node_id!r} has no {input_name!r} input.")
    inputs[input_name] = value


def parse_setting(value: str) -> tuple[str, str, Any]:
    try:
        node_and_input, raw_value = value.split("=", 1)
        node_id, input_name = node_and_input.split(".", 1)
    except ValueError as error:
        raise argparse.ArgumentTypeError("Use NODE_ID.INPUT=VALUE.") from error
    try:
        parsed_value = json.loads(raw_value)
    except json.JSONDecodeError:
        parsed_value = raw_value
    return node_id, input_name, parsed_value


def load_project(path: Path) -> dict[str, Any]:
    try:
        project = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as error:
        raise ValueError(f"Cannot read project file: {error}") from error
    if not isinstance(project, dict):
        raise ValueError("Project file must contain a JSON object.")
    if "workflow" not in project:
        raise ValueError("Project file requires a 'workflow' path.")
    if not isinstance(project.get("nodes", {}), dict) or not isinstance(project.get("defaults", {}), dict):
        raise ValueError("Project 'nodes' and 'defaults' must be JSON objects.")
    return project


def project_path(project_file: Path, value: str | Path) -> Path:
    path = Path(value)
    return path if path.is_absolute() else project_file.parent / path


def download_outputs(server: str, history: dict[str, Any], output_dir: Path) -> list[Path]:
    output_dir.mkdir(parents=True, exist_ok=True)
    saved: list[Path] = []
    for node_output in history.get("outputs", {}).values():
        for image in node_output.get("images", []):
            filename = image["filename"]
            query = urlencode({
                "filename": filename,
                "subfolder": image.get("subfolder", ""),
                "type": image.get("type", "output"),
            })
            target = output_dir / Path(filename).name
            with urlopen(f"{server}/view?{query}", timeout=60) as response, target.open("wb") as file:
                shutil.copyfileobj(response, file)
            saved.append(target)
    return saved


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--project", type=Path, help="Project JSON with workflow, nodes, and generation defaults")
    parser.add_argument("--root-dir", type=Path, default=Path.cwd(), help="Project root containing comfy-image/")
    parser.add_argument("--workflow", type=Path, help="ComfyUI API-format JSON workflow")
    parser.add_argument("--prompt", required=True)
    parser.add_argument("--negative-prompt")
    parser.add_argument("--positive-node")
    parser.add_argument("--negative-node")
    parser.add_argument("--seed-node")
    parser.add_argument("--seed", type=int)
    parser.add_argument("--set", dest="settings", action="append", default=[], type=parse_setting)
    parser.add_argument("--server", default="http://127.0.0.1:8188")
    parser.add_argument("--output-dir", type=Path)
    parser.add_argument("--timeout", type=float, default=300)
    parser.add_argument("--dry-run", action="store_true", help="Print resolved inputs without submitting a job")
    args = parser.parse_args()

    project: dict[str, Any] = {}
    defaults: dict[str, Any] = {}
    project_file: Path | None = None
    if args.project is None:
        default_project = args.root_dir.resolve() / "comfy-image" / "comfy-image.project.json"
        if default_project.is_file():
            args.project = default_project
    if args.project:
        project_file = args.project.resolve()
        try:
            project = load_project(project_file)
        except ValueError as error:
            parser.error(str(error))
        defaults = project["defaults"]
        nodes = project.get("nodes", {})
        if args.workflow is None:
            args.workflow = project_path(project_file, project["workflow"])
        for argument, key in (("positive_node", "positive"), ("negative_node", "negative"), ("seed_node", "seed")):
            if getattr(args, argument) is None and key in nodes:
                setattr(args, argument, str(nodes[key]))
        if args.seed is None and "seed" in defaults:
            args.seed = int(defaults["seed"])
        if args.negative_prompt is None:
            args.negative_prompt = str(defaults.get("negative_prompt", ""))
        if args.output_dir is None:
            args.output_dir = project_path(project_file, defaults.get("output_dir", "outputs"))

    if args.workflow is None:
        parser.error("Provide --workflow or --project.")
    if args.negative_prompt is None:
        args.negative_prompt = ""
    if args.output_dir is None:
        args.output_dir = Path("outputs")

    settings: dict[tuple[str, str], Any] = {}
    for setting, value in defaults.get("settings", {}).items():
        try:
            node_id, input_name, _ = parse_setting(f"{setting}=null")
        except argparse.ArgumentTypeError as error:
            parser.error(f"Invalid project default setting {setting!r}: {error}")
        settings[(node_id, input_name)] = value
    for node_id, input_name, value in args.settings:
        settings[(node_id, input_name)] = value

    server = args.server.rstrip("/")
    if not server.startswith("http://127.0.0.1") and not server.startswith("http://localhost"):
        parser.error("Refusing a non-local server. Use localhost unless explicitly changing this script.")
    try:
        workflow = json.loads(args.workflow.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as error:
        parser.error(f"Cannot read API-format workflow: {error}")

    try:
        set_input(workflow, args.positive_node, "text", args.prompt)
        set_input(workflow, args.negative_node, "text", args.negative_prompt)
        if args.seed is not None:
            set_input(workflow, args.seed_node, "seed", args.seed)
        for (node_id, input_name), value in settings.items():
            set_input(workflow, node_id, input_name, value)
        if args.dry_run:
            print(json.dumps({
                "workflow": str(args.workflow.resolve()),
                "project": str(project_file) if project_file else None,
                "seed": args.seed,
                "output_dir": str(args.output_dir.resolve()),
                "settings": {f"{node}.{input_name}": value for (node, input_name), value in settings.items()},
            }, ensure_ascii=False, indent=2))
            return 0
        queued = request_json(f"{server}/prompt", method="POST", payload={"prompt": workflow, "client_id": str(uuid.uuid4())})
    except (RuntimeError, ValueError) as error:
        print(f"error: {error}", file=sys.stderr)
        return 1
    if "prompt_id" not in queued:
        print(json.dumps(queued, ensure_ascii=False, indent=2), file=sys.stderr)
        return 1

    prompt_id = queued["prompt_id"]
    print(f"Queued ComfyUI prompt: {prompt_id}")
    deadline = time.monotonic() + args.timeout
    while time.monotonic() < deadline:
        try:
            history = request_json(f"{server}/history/{prompt_id}")
        except RuntimeError as error:
            print(f"error: {error}", file=sys.stderr)
            return 1
        completed = history.get(prompt_id)
        if completed:
            saved = download_outputs(server, completed, args.output_dir)
            if not saved:
                print("Completed, but no image outputs were returned.", file=sys.stderr)
                return 1
            for path in saved:
                print(path.resolve())
            return 0
        time.sleep(0.5)
    print(f"Timed out waiting for {prompt_id} after {args.timeout:g} seconds.", file=sys.stderr)
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
