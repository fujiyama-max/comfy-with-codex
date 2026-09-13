#!/usr/bin/env bash
# Install the bundled Codex skill and a local ComfyUI workspace.
set -euo pipefail

repo_root="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
codex_home="${CODEX_HOME:-$HOME/.codex}"
skill_source="$repo_root/skills/comfy-image"
skill_target="$codex_home/skills/comfy-image"
comfy_workspace="${COMFY_WORKSPACE:-$HOME/comfy-image-comfyui}"
python_bin="${PYTHON_BIN:-python3}"
model_url=""

usage() {
  cat <<'USAGE'
Usage: ./setup.sh [options]

Install the bundled comfy-image skill and a local ComfyUI workspace.

Options:
  --comfy-workspace PATH  Install or reuse ComfyUI in PATH/ComfyUI.
                           Default: ~/comfy-image-comfyui
  --model-url URL         Download a checkpoint after installation.
                           The URL must point to a model file you are allowed to download.
  --skip-comfyui          Install only the Codex skill.
  -h, --help              Show this help.

Environment variables:
  CODEX_HOME       Codex home directory. Default: ~/.codex
  COMFY_WORKSPACE  Same as --comfy-workspace.
  PYTHON_BIN       Python 3.10+ executable. Default: python3
USAGE
}

install_comfyui=1
while [[ $# -gt 0 ]]; do
  case "$1" in
    --comfy-workspace)
      [[ $# -ge 2 ]] || { echo "error: --comfy-workspace requires a path" >&2; exit 2; }
      comfy_workspace="$2"
      shift 2
      ;;
    --model-url)
      [[ $# -ge 2 ]] || { echo "error: --model-url requires a URL" >&2; exit 2; }
      model_url="$2"
      shift 2
      ;;
    --skip-comfyui)
      install_comfyui=0
      shift
      ;;
    -h|--help)
      usage
      exit 0
      ;;
    *)
      echo "error: unknown option: $1" >&2
      usage >&2
      exit 2
      ;;
  esac
done

[[ -f "$skill_source/SKILL.md" ]] || { echo "error: bundled skill is missing: $skill_source" >&2; exit 1; }

mkdir -p "$skill_target/agents" "$skill_target/scripts"
cp "$skill_source/SKILL.md" "$skill_target/SKILL.md"
cp -R "$skill_source/agents/." "$skill_target/agents/"
cp -R "$skill_source/scripts/." "$skill_target/scripts/"
echo "Installed Codex skill: $skill_target"

if [[ "$install_comfyui" -eq 0 ]]; then
  exit 0
fi

command -v git >/dev/null || { echo "error: Git is required. Install Git and retry." >&2; exit 1; }
command -v "$python_bin" >/dev/null || { echo "error: Python 3.10+ is required. Set PYTHON_BIN if needed." >&2; exit 1; }

"$python_bin" - <<'PY'
import sys
if sys.version_info < (3, 10):
    raise SystemExit("error: Python 3.10 or later is required")
PY

mkdir -p "$comfy_workspace"
venv_dir="$comfy_workspace/.venv"
if [[ ! -x "$venv_dir/bin/python" ]]; then
  "$python_bin" -m venv "$venv_dir"
fi

"$venv_dir/bin/python" -m pip install --upgrade pip comfy-cli
"$venv_dir/bin/comfy" --skip-prompt --workspace "$comfy_workspace" install

echo "Installed ComfyUI workspace: $comfy_workspace/ComfyUI"
echo "Start it with: $venv_dir/bin/comfy --workspace $comfy_workspace launch -- --lowvram"

if [[ -n "$model_url" ]]; then
  "$venv_dir/bin/comfy" --workspace "$comfy_workspace" model download --url "$model_url" --relative-path models/checkpoints
  echo "Downloaded model into: $comfy_workspace/ComfyUI/models/checkpoints"
else
  cat <<'NEXT'
No model was downloaded. Download a compatible checkpoint only after accepting its license, for example:
  ./setup.sh --model-url 'https://example.invalid/model.safetensors'
Then set the downloaded filename in comfy-image/comfy-image.project.json.
NEXT
fi
