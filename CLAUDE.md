# CLAUDE.md — AI向けプロジェクトガイド

Wood Puzzle（シルエットにピースをはめるパズル）。Python + Pygame を Pygbag で WebAssembly 化し、
GitHub Pages で公開している。構成の全体像は [REPO_MAP.md](REPO_MAP.md)、経緯は [ROADMAP.md](ROADMAP.md)。

---

## ⚠️ 最重要: 起動スクリプトの混同に注意喚起すること

**ユーザーは `run.bat` と `run_with_pygbag.bat` を混同しやすい。**
Web版の動作確認を伴う作業では、AIから能動的に「どちらを実行するか」を確認・注意喚起すること。

実際に2026-07-17、Web版の確認で `run_with_pygbag.bat` を使うべきところ `run.bat` を実行してしまい、
原因調査に長時間を要した（ブラウザ側が更新中だった可能性も併発）。

紛らわしい理由は名前だけではない。**同じ `run.bat` が時期によって別物になっている**:

| ファイル | 当時（公開中apk内に保存されている版） | 現在の作業ディレクトリ |
|---|---|---|
| `run.bat` | `python main.py`（**デスクトップ版**。Webサーバーではない） | `python -m pygbag .`（**Web開発サーバー**） |
| `run_with_pygbag.bat` | `python -m pygbag .`（Web開発サーバー） | **存在しない** |
| `local_test_run.bat` | `python -m pygbag .`（Web開発サーバー） | **存在しない** |
| `build_web.bat` | `python -m pygbag --build .` + GA4注入 | **存在しない** |

つまり「run.bat を実行してください」という案内は、**どの版の run.bat か**で意味が変わる。
案内する時は必ず**中身（コマンド）を確認してから**、コマンド自体を提示すること。

---

## Web版の動かし方

```bash
# ローカル確認（Pygbag開発サーバー。archives/ 等を自前で配信するのでこれが確実）
python -m pygbag .          # → http://localhost:8000/
```

- **注意**: 開発サーバーは `build/web/index.html` を上書きし、GA4タグを消す。
- 公開用の成果物を作る時だけ、ビルドと注入を順に実行する:

```bash
python -m pygbag --build .              # → build/web/
python assets/scripts/inject_ga4.py     # GA4タグ・タイトル・ローディング文言を注入
```

- デプロイは `build/web/*`（`index.html`, `woodpazzule.apk`, `favicon.png`, `privacy.html`）を
  **リポジトリ直下へコピー**して push する。GitHub Pages が配信しているのは直下のファイル。
  `build/` 自体は `.gitignore` 済み。

### ブラウザで確認する時

- **ゲーム本体は `index.html` ではなく `woodpazzule.apk` の中**（Pygbagがソースをzipで固めたもの）。
  `src/*.py` を編集しても**再ビルドするまでブラウザには反映されない**。
- apkは約3.6MB。古いものがキャッシュされることがあるので Ctrl+F5 を促す。
- ブラウザ（Chrome）が更新中だと起動しないことがある。動かない時はまずこれを疑う。

---

## Web版（Pygbag）固有の制約

### GA4イベント送信は保留中（`src/analytics.py`）

**Web版では絶対にJS側の `gtag` / `window.eval()` を呼ばないこと。** ゲームループがブロックされフリーズする。
`AnalyticsManager.send_event()` はWeb版では即 `return` する。この方針は ROADMAP フェーズ6-3で採用され、
フェーズ6-4で再実装を試みて**再びフリーズしたため中断**した経緯がある。安易に「復活」させない。

- PV計測は `assets/scripts/inject_ga4.py` が `index.html` に入れるGA4タグが行う（Python側は不要）。
- `send_event()` は例外を投げない設計なので、呼び出し側で try/except を巻かないこと。

### その他

- `await asyncio.sleep(0)` はメインループの**最後に1回だけ**。時間指定（`sleep(0.016)` 等）は不可。
- `pygame.time.wait()` / `time.sleep()` / `clock.tick()` 依存は不可。
- WASM上ではオブジェクト生成が重い。毎フレームの `Surface`/`Rect`/フォント生成やレンダリングは避け、
  キャッシュする。描画キャッシュの破棄は `Game._invalidate_render_cache()` に集約してある。

---

## ⚠️ 作業ディレクトリから失われているファイル

以下は**公開中のゲームには含まれるが、作業ディレクトリに存在しない**（2026-07-17時点、未解決）:

- `stages/STAGE_001.stage` 〜 `STAGE_020.stage`（**20ステージ全部**）
- `assets/data/text_en.json`, `text_ja.json`（UIテキスト）
- `assets/fonts/NotoSansJP-Regular.ttf`（日本語フォント）
- `assets/SE/snap.wav`, `clear.wav`（効果音）
- `assets/privacy.html`、`build_web.bat`、`local_test_run.bat`、`run_with_pygbag.bat`、`requirements.txt` ほか

**結果として、現状ビルドすると「内蔵Stage 1のみ・UIテキストは `ui.clear` 等のキー文字列・音なし」になる。**
この状態を**絶対にデプロイしないこと**（20ステージのゲームが1ステージに置き換わる）。

これらは**リポジトリ直下の `woodpazzule.apk`（公開中の版）の中に全て残っている**ので復元可能:

```python
import zipfile
zipfile.ZipFile('woodpazzule.apk').extractall('復元先')   # assets/ 以下に入っている
```

---

## デプロイ前チェック

`src/*.py` を直しただけで「検証OK」としないこと。**ビルド成果物の中身を公開中の版と比較する**。

```python
import zipfile
z = zipfile.ZipFile('build/web/woodpazzule.apk')
z.namelist()          # stages/ や assets/data/ が入っているか
```

- [ ] apkに `stages/STAGE_001〜020.stage` が入っているか
- [ ] apkに `assets/data/text_*.json`, `assets/fonts/*.ttf`, `assets/SE/*.wav` が入っているか
- [ ] `analytics.py` がWeb版で `gtag` を呼んでいないか
- [ ] `inject_ga4.py` を実行済みか（GA4タグ・タイトル・ローディング文言）
- [ ] 実ブラウザで起動・プレイできるか（ヘッドレステストではWeb版の描画は検証できない）

---

## バージョン

`src/__init__.py` の `__version__` が正（現在 1.1）。
`build/version.txt` の `0.9.2` は **Pygbagのバージョン**でありアプリのものではない。混同しないこと。
