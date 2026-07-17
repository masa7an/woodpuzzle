# Wood Puzzle - リポジトリマップ

シルエットにピースをはめ込むパズルゲーム（Python + Pygame → Pygbagで WebAssembly化）。
[README.md](./README.md) がプレイ方法、[ROADMAP.md](./ROADMAP.md) が開発経緯・機能履歴。このファイルはコードとディレクトリの構成を俯瞰するための地図。

---

## 全体構成

```
woodpazzule/
├── main.py              # エントリーポイント（asyncio起動 → Game.run()）
├── src/                  # ゲーム本体のPythonモジュール
├── assets/               # ビルド・データ生成用スクリプト（画像/音声/データは未生成）
├── build/                # Pygbagビルド出力（配布物・生成物）
├── index.html / favicon.png / privacy.html  # ローカル実行用の静的ファイル（build/web内と重複）
├── ranking.json          # デスクトップ版のローカルランキング保存先
├── run.bat               # `python -m pygbag .` を起動するWindows用スクリプト
├── woodpazzule.apk       # Android向けビルド成果物（配布物）
├── README.md / ROADMAP.md
└── debug.log             # 実行時ログ（生成物）
```

## Git管理状況（注意）

`git status` 時点で `src/`, `assets/`, `build/`, `main.py`, `run.bat`, `ranking.json`, `debug.log` はすべて **未追跡（`??`）**。
リポジトリに `git ls-files` で登録されているのは `README.md`, `ROADMAP.md`, `favicon.png`, `index.html`, `privacy.html`, `screenshot.jpg`, `woodpazzule.apk` のみで、**ゲーム本体のソースコードがまだコミットされていない**状態。

---

## `src/` — ゲーム本体（合計 約2,450行）

| ファイル | 行数 | 役割 |
|---|---|---|
| [game.py](src/game.py) | 1788 | `Game`クラス。メインループ・入力処理・描画・ステージ管理・エディタモード・ランキング・タイマーなど、大半のロジックが集約された中核ファイル |
| [piece.py](src/piece.py) | 219 | `Piece`クラス。ピースのドラッグ操作、グリッドへの配置判定・着脱 |
| [stage_loader.py](src/stage_loader.py) | 134 | `StageLoader`。独自テキスト形式 `.stage` ファイルの読み書き（`stages/`ディレクトリを想定） |
| [grid.py](src/grid.py) | 93 | `Grid`クラス。2Dグリッド（1=有効セル/0=無効セル）の管理、セル⇔ピクセル変換、完成判定 |
| [text_manager.py](src/text_manager.py) | 72 | `TextManager`（シングルトン `text_manager`）。`assets/data/text_{lang}.json` を読み込む多言語対応 |
| [sound.py](src/sound.py) | 69 | `SoundManager`（シングルトン `sound_manager`）。`assets/SE/snap.wav`, `clear.wav` の再生 |
| [analytics.py](src/analytics.py) | 83 | `AnalyticsManager`（シングルトン `analytics`）。GA4送信。Web(emscripten)は `platform.window.gtag` 経由、デスクトップはコンソールログのみ |
| [__init__.py](src/__init__.py) | 1 | パッケージマーカー |

### `Game`クラスの主な責務（[game.py](src/game.py)）
- **初期化/リソース**: `init()`, `_update_fonts()`, `_refresh_text_surfaces()`
- **ステージ管理**: `_load_stage1()`（内蔵のStage1定義）, `_load_stage_from_file()`, `_setup_stage()`, `_load_stage()`, `_check_next_stage_exists()`, `_load_next_stage()`
- **入力処理**: `handle_events()`, `_on_mouse_down/up/move()`, `_handle_instruction_tap()`（スマホタップ対応）
- **アンドゥ**: `_capture_piece_state()`, `_undo_last_action()`
- **エディタモード**（Eキー）: `_toggle_editor_mode()`, `_editor_new_stage()`, `_editor_load_stage()`, `_editor_click()`, `_print_design()`
- **ランキング**: `_load_ranking()`, `_save_ranking()`, `_update_ranking()`（`ranking.json` に保存、Web版は`localStorage`）
- **描画**: `draw()`, `_draw_editor()`, `_draw_clear_message()`, `_draw_placeable_highlight()`, `_draw_ghost()`, `_draw_timer()`, `_draw_title_screen()`, `_draw_instructions()`, `_draw_privacy_policy()` 等

---

## `assets/` — 生成・ビルド支援スクリプト（成果物は未コミット/未生成）

| ファイル | 役割 |
|---|---|
| [generate_stages.py](assets/generate_stages.py) | ステージ形状（11x11グリッド）とピース分割をプログラムで生成し、`stages/*.stage` として出力するツール。将来ステージ案（Apple, Mushroom, Umbrella等）の形状定義を含む |
| [generate_stages_doc.py](assets/generate_stages_doc.py) | ステージ定義からドキュメントを生成するツール（詳細未確認） |
| [scripts/inject_ga4.py](assets/scripts/inject_ga4.py) | Pygbagビルド後の `build/web/index.html` にGA4タグとローディングUI修正を注入するポストビルドスクリプト |

**注意**: コードが参照している以下のパスは現在リポジトリ上に存在しない（実行時に生成 or 別途配置が必要）:
- `stages/*.stage`（[stage_loader.py:59](src/stage_loader.py)、`assets/generate_stages.py`の出力先）
- `assets/data/text_en.json`, `assets/data/text_ja.json`（[text_manager.py:20](src/text_manager.py)）
- `assets/SE/snap.wav`, `assets/SE/clear.wav`（[sound.py:35](src/sound.py)）

---

## `build/` — Pygbag ビルド出力（生成物）

- `build/web/index.html`, `favicon.png`, `privacy.html`, `woodpazzule.apk` — GitHub Pages にデプロイされる静的ファイル一式
- `build/web-cache/` — Pygbagが生成するキャッシュ（`.data`/`.head`/`.tmpl`等）
- `build/version.txt` — Pygbagのバージョン（`0.9.2`）

デプロイ先: https://masa7an.github.io/woodpuzzle/ （README記載）

---

## 実行・ビルドフロー

1. **ローカル実行（デスクトップ）**: `python main.py`（`src.game.Game` を `asyncio` で起動）
2. **ローカルWebテスト**: [run.bat](run.bat) → `python -m pygbag .` で `http://localhost:8000/` にサーバ起動
3. **Web本番ビルド後処理**: `assets/scripts/inject_ga4.py` を実行し `build/web/index.html` にGA4タグ注入・UME待機ループのタイムアウト追加・タイトル変更
4. **配布**: `build/web/` を GitHub Pages にプッシュ

---

## 技術的な注意点（ROADMAPより）

- Web版（Pygbag/emscripten）で `window.eval()` を使うとゲームループがフリーズする既知の問題があり、Analytics実装は `platform.window.gtag` 直接呼び出し + エラーハンドリングで回避（[analytics.py](src/analytics.py)）。GA4カスタムイベント送信は現状フリーズのため無効化中、PV計測のみ有効。
- 回転・反転機能は未実装（スコープ外として明示的に見送り）。
- Stage 11〜20 は形状候補のみ [generate_stages.py](assets/generate_stages.py) にあり、未実装。
