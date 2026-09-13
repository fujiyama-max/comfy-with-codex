---
name: comfy-image
description: "Generate images through a local ComfyUI server instead of Codex image generation. Use when a user asks to create, generate, render, iterate on, or edit an image and ComfyUI should receive an optimized prompt and workflow parameters."
---

# Comfy Image

Turn the user's visual request into a ComfyUI prompt, execute it on the local ComfyUI server, and return the saved image paths. Do not use Codex's built-in image generation for this task.

## Workflow

1. Treat the current project root as the scope. Keep API-format workflow templates in `<root>/workflows/`, not in this global skill. Use `<root>/comfy-image/` only for this project's Comfy settings and generated media. Inspect `<root>/comfy-image/comfy-image.project.json` first. When it exists, use its workflow, node IDs, seed, settings, model settings, and output directory. Otherwise, inspect `workflows/*.json`, then create that project file and `<root>/comfy-image/outputs/` after a usable API-format workflow is known. Do not put generated images in the repository root.
2. Translate the request into a concise positive prompt. Preserve stated subject, composition, style, lighting, palette, camera/framing, text, aspect ratio, and reference-image constraints. Do not invent branded characters, unreadable text, or unsupported model features.
3. Generate at FHD (1920×1080) by default. Use 1080×1920 only when the user explicitly requests a vertical composition; honor any explicit size or aspect-ratio request instead. For constrained local hardware, warn before reducing this default.
4. Write a short negative prompt only when it helps the chosen workflow. Include the final positive prompt, negative prompt, workflow path, seed, and size in the response before executing if any of them is inferred rather than supplied.
5. Use `scripts/run_comfy.py` to set the text, seed, and image dimensions, submit to the local server, wait for completion, and download the output(s).
6. Inspect the generated image when available. If it misses a material requirement, explain the mismatch and offer a focused retry with changed prompt or parameters; do not silently run repeated generations.

## Run a workflow

Start ComfyUI separately (usually `comfy launch`) and keep it bound to localhost. Submit only to `http://127.0.0.1:8188` unless the user explicitly authorizes another host.

Use explicit node IDs from the exported API workflow. The script changes only the inputs named below, leaving sampler/model wiring intact.

```bash
python3 "$HOME/.codex/skills/comfy-image/scripts/run_comfy.py" \
  --workflow workflows/base_api.json \
  --positive-node 6 \
  --negative-node 7 \
  --seed-node 3 \
  --prompt "editorial product photograph of a red ceramic mug on pale limestone, soft window light, 85mm lens" \
  --negative-prompt "text, watermark, blurry, distorted" \
  --seed 481516 \
  --set 4.width=1920 \
  --set 4.height=1080 \
  --output-dir outputs
```

Use `--set NODE_ID.INPUT=VALUE` for other safe widget values, such as `--set 3.steps=28` or `--set 5.width=1920`. Use this only after inspecting the workflow JSON and confirming that the node input exists.

## Project defaults

Place `comfy-image.project.json` in `<root>/comfy-image/` to preserve project-specific generation settings. Resolve relative paths from that file. Use `outputs` as the output directory value so images remain under `<root>/comfy-image/outputs/`. Let an explicit CLI option override the project default.

Keep each project's models in its own workflow/configuration. The model must be installed in the local ComfyUI model directory, and the project configuration must set the checkpoint node input (usually `CheckpointLoaderSimple.ckpt_name`) through `defaults.settings`. Never substitute a model merely because it is installed: report the missing configured model and ask whether to install it or choose an available one.

```json
{
  "workflow": "../workflows/animagine-xl-api.json",
  "nodes": { "positive": "2", "negative": "3", "seed": "5" },
  "defaults": {
    "seed": 739204681,
    "negative_prompt": "lowres, blurry, bad anatomy, text, watermark",
    "output_dir": "outputs",
    "settings": {
      "1.ckpt_name": "animagine-xl-4.0-opt.safetensors",
      "4.width": 1920,
      "4.height": 1080,
      "5.steps": 20,
      "5.cfg": 5.0
    }
  }
}
```

When invoked from the project root, run with `--prompt "..."`; the script discovers `comfy-image/comfy-image.project.json` automatically. Use `--project <path>` for an explicit settings file, `--root-dir <root>` for another root, and `--dry-run` to inspect the resolved workflow and values without queuing an image.

## Input images and edits

For img2img, inpainting, or reference workflows, first place or upload the user-provided image according to the workflow's `LoadImage` node requirements. Do not claim an edit succeeded until the downloaded output is present. Keep the original asset unchanged.

## Failure handling

- If the server is unavailable, report the exact URL and suggest `comfy launch`; do not fall back to paid/hosted generation.
- If `/prompt` returns validation errors, report the failing node(s), then inspect the template, installed custom nodes, and model names before changing anything.
- Keep API-format workflow templates in the user's repository, not inside this global skill.
