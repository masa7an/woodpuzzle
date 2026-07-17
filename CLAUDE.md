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
build_web.bat        # ビルド + GA4注入をまとめて実行（下記の罠も処理する）
```

### ⚠️ 罠: 直下の `woodpazzule.apk` を退避せずにビルドすると、apkが自分自身を同梱する

pygbagは**プロジェクト直下を丸ごとパックし、`.apk` を除外しない**
（`pygbag/filtering.py` の `SKIP_EXT` は `lnk, pyc, pyx, pyd, pyi, exe, bak, log, blend` のみ。
除外フォルダは `/build`, `/dist`, `/.git`, `/venv`, `/ignore`, `/static`, `/ATTIC` 等）。

直下の `woodpazzule.apk` は GitHub Pages が配信している**公開中の成果物**なので、
置いたままビルドすると新しいapkの中に古いapkが丸ごと入り、**サイズが約2倍**になる（3.6MB → 7.1MB）。

`build_web.bat` は一時的に `woodpazzule.apk.bak` へリネームして回避している
（`.bak` は `SKIP_EXT` に含まれるためパックされない）。手動でビルドする場合も同じ退避が必要:

```bash
mv woodpazzule.apk woodpazzule.apk.bak
python -m pygbag --build .
mv woodpazzule.apk.bak woodpazzule.apk
python assets/scripts/inject_ga4.py
```

**ビルド後は必ずapkのサイズと中身を確認すること**（公開中の3.5MBから大きく増えていたら疑う）。

### ⚠️ push してもGitHub Pagesのデプロイが走らないことがある

**症状**: `git push` は成功し、GitHub側にもコミットが届いている（リモートの `main` が新しいsha、
`pushed_at` も更新済み）のに、`pages build and deployment` の実行が**1件も作られない**。
ビルド失敗ではなく**未起動**なので、失敗通知メールも来ない。公開サイトは旧版のまま。

**対処**: **もう一度 push すれば起動する。** 2026-07-17の実例:

| | 1回目 push | 2回目 push |
|---|---|---|
| ワークフロー起動 | **0件**（20分待っても） | **30秒以内に起動** → success → 公開反映 |

この間、設定は一切変えていない。

**原因は未確定。** ユーザーの仮説は「**公開デプロイはサインイン済みでないと動かない可能性**」。
実際、1回目と2回目の間にユーザーがGitHubへサインインし Settings→Pages / Settings→Actions を開いている。
設定画面を開いたことでPagesが再登録された可能性もあり、サインイン自体が要因かは切り分けできていない。
Dec 2025から約7ヶ月の休眠明けだったことも関係するかもしれない（いずれも推測）。

**確認方法**（publicリポジトリなので未認証のAPIで見える。`gh` CLIは未インストール）:

```bash
# ワークフロー実行履歴（今日のpushで新しい実行が増えているか）
curl -s "https://api.github.com/repos/masa7an/woodpuzzle/actions/runs?per_page=3"
# 公開中のapkが手元と同じサイズか
curl -sI "https://masa7an.github.io/woodpuzzle/woodpazzule.apk" | grep -i content-length
```

**切り分け済みで原因ではないもの**（同じ道を辿らないこと）:

- `.github/workflows/` が無いこと → **正常**。Pages Sourceが `Deploy from a branch` の場合、
  GitHubが組み込みの `pages-build-deployment` を自動実行する。ワークフローファイルは不要。
  （`GitHub Actions` を選んでいる場合のみ必要）
- Actions permissions → `Allow all actions and reusable workflows` で有効だった
- ワークフローの state → `active`（休眠による自動無効化ではなかった）
- Pages Source → `main` / `(root)` で正しかった
- リポジトリ → public / アーカイブなし / 無効化なし

---

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

## 失われていたファイルについて（2026-07-17 復元済み）

`stages/`（20ステージ）、`assets/data/`（UIテキスト）、`assets/fonts/`（日本語フォント）、
`assets/SE/`（効果音）は作業ディレクトリから消えていたが、公開中の `woodpazzule.apk` から復元しGit管理下に入れた。

**まだ復元していないもの**（必要になったら同じくapkから取り出せる）:
`assets/privacy.html`（直下の `privacy.html` は存在する）、`local_test_run.bat`、
`run_with_pygbag.bat`、`requirements.txt`、`stages.md`、`pygbag_web移植ガイド.md`

公開中のapkは事実上のバックアップとして機能する:

```python
import zipfile
zipfile.ZipFile('woodpazzule.apk').extractall('復元先')   # assets/<元の直下> という構造
```

**教訓**: `src/*.py` を直しただけで「検証OK」としないこと。ビルド成果物（apk）の中身を
公開中の版と必ず比較する。アセットが欠けたままデプロイすると、20ステージのゲームが
1ステージ・テキスト無しに置き換わる。

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
- [ ] apkが自分自身（`assets/woodpazzule.apk`）を同梱していないか
- [ ] `analytics.py` がWeb版で `gtag` を呼んでいないか
- [ ] `inject_ga4.py` を実行済みか（GA4タグ・**タイトルのバージョン**・ローディング文言）
- [ ] 実ブラウザで起動・プレイできるか（ヘッドレステストではWeb版の描画は検証できない）

## デプロイ後チェック

push しただけで「公開した」と言わないこと。**必ず公開サイト側を確認する**
（上記のとおりPagesが起動しないことがある）:

- [ ] ワークフローが起動し success したか（未起動ならもう一度 push）
- [ ] 公開中のapkが手元と同じか（サイズ or SHA256の一致）
- [ ] タブのタイトルに新しいバージョンが出るか（人が新旧を見分ける唯一の手段）

バージョンはタイトルの2箇所に入る。**片方だけに頼らない**:

- `index.html` の `<title>` — `inject_ga4.py` がビルド時に注入。Pythonが動く前から見える（確実）
- `pygame.display.set_caption()` — `Game._window_caption()`。デスクトップでは確認済みだが、
  **Web版でタブへ反映されるかは未検証**

---

## バージョン

`src/__init__.py` の `__version__` が正（現在 1.1）。
`build/version.txt` の `0.9.2` は **Pygbagのバージョン**でありアプリのものではない。混同しないこと。
