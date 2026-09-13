# `comfy-image` セットアップ

リポジトリをcloneした後、`setup.sh` を実行すると、同梱された `comfy-image` スキルをCodexのスキルディレクトリへ配置し、ローカルComfyUIワークスペースを導入します。

## 前提条件

- macOS、Linux、またはWSL
- Git
- Python 3.10以降
- Codex
- モデルを保存できる十分な空きディスク容量

Macでは、Apple Silicon環境でComfyUIを動かせます。GPU・メモリ量に応じて、初回の依存関係インストールやFHD生成には時間がかかります。

## クイックスタート

```sh
git clone <repository-url> comfy-with-codex
cd comfy-with-codex
./setup.sh
```

この操作により次を行います。

1. `skills/comfy-image/` を `~/.codex/skills/comfy-image/` へコピー
2. `~/comfy-image-comfyui/.venv/` に専用Python環境を作成
3. Comfy CLIをインストール
4. `~/comfy-image-comfyui/ComfyUI/` にComfyUIとComfyUI-Managerをインストール

ComfyUIの導入先を変えるには、`--comfy-workspace` を指定します。

```sh
./setup.sh --comfy-workspace "$HOME/Applications/comfy-image"
```

スキルだけを更新する場合は次を使います。

```sh
./setup.sh --skip-comfyui
```

## モデルを導入する

モデルはサイズが大きく、ライセンス条件もモデルごとに異なるため、標準のセットアップでは自動ダウンロードしません。利用条件を確認済みのモデルURLを指定してダウンロードします。

```sh
./setup.sh --model-url 'https://<model-host>/<model>.safetensors'
```

ダウンロード後、`comfy-image/comfy-image.project.json` の `1.ckpt_name` を、`models/checkpoints/` に保存されたモデルファイル名へ合わせます。ワークフロー自体も対象モデルに対応している必要があります。

## ComfyUIを起動する

```sh
$HOME/comfy-image-comfyui/.venv/bin/comfy \
  --workspace "$HOME/comfy-image-comfyui" launch -- --lowvram
```

起動後、ブラウザで `http://127.0.0.1:8188` を開くとワークフローとキューを確認できます。

## プロジェクト設定

[comfy-image/comfy-image.project.json](comfy-image/comfy-image.project.json) が、このプロジェクトの既定値です。

```json
{
  "workflow": "../workflows/animagine-xl-api.json",
  "nodes": { "positive": "2", "negative": "3", "seed": "5" },
  "defaults": {
    "seed": 739204681,
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

- `workflow`: このプロジェクトで使う API形式ワークフロー
- `nodes`: プロンプトとseedを設定するノードID
- `seed`: 同じ設定で再現可能にする既定seed
- `1.ckpt_name`: `CheckpointLoaderSimple` が使うモデルファイル名
- `4.width` / `4.height`: 既定のFHDサイズ（1920×1080）

モデルを変える場合は、対応するワークフローと `ckpt_name` を一緒に更新してください。ノードIDはワークフローごとに異なるため、API JSONを確認してから設定します。

## Codex から生成する

ComfyUIを起動した後、このプロジェクトを開いたCodexで次のように依頼します。

```text
/comfy-image 夕暮れの海辺を歩くアニメ風の少年を生成して
```

スキルは `comfy-image/comfy-image.project.json` を自動検出し、設定済みのワークフロー・モデル・seedで生成します。生成画像は `comfy-image/outputs/` に保存されます。

## 新しいプロジェクトへ適用する

別のプロジェクトでも、以下を用意すれば同じスキルを利用できます。

1. `workflows/` に ComfyUI の **Save (API Format)** で書き出したJSONを置く。
2. `comfy-image/comfy-image.project.json` を作成する。
3. ワークフローのノードID、チェックポイント、seed、サイズ、サンプラー設定をプロジェクト用に指定する。
4. ComfyUIを起動し、プロジェクトルートから `/comfy-image` を呼び出す。

ワークフローやモデルはグローバルスキルに同梱せず、プロジェクト側で管理します。これにより、プロジェクトごとに画風・モデル・seedを独立して固定できます。

## 参考

Comfy CLIによるComfyUIの導入とモデル管理は、公式の[Comfy CLIクイックスタート](https://docs.comfy.org/ja/comfy-cli/getting-started)を参照してください。
