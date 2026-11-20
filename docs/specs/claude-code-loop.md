# Claude Code による Issue 駆動ループ

状態: 承認済み（2026-11-20、Pull Request 6 番のマージによる）

## 背景と目的

Issue 駆動の運用（[Issue 駆動開発ガイド](../guides/issue-driven-sdd.md)）は、手順（[WORKFLOW.md](../../WORKFLOW.md)）、行動規範（[ethics/](../../ethics/README.md)）、ラベル、CI まで定義済みです。しかし、Issue を拾って実装するランナーがありません。WORKFLOW.md が前提とする Symphony の参照実装は Codex を前提にしており、常駐プロセスの構築とトークンの設定が必要です。

追加のインフラを用意せずに、手元の Claude Code だけで Issue 駆動のサイクルを回せるようにします。

## 作るもの

| 名前 | 内容 |
|---|---|
| `/sdd-run` | 1 周分の実行。着手できる Issue を 1 件選び、WORKFLOW.md の手順をその Issue について進める |
| `/loop <間隔> /sdd-run` | Claude Code の `/loop` で `/sdd-run` を繰り返す。新しく作るものではなく、使い方として定める |

`/sdd-run` は、Symphony ランナーの代わりに「Issue を選ぶ」「WORKFLOW.md のプロンプトに Issue の情報を当てはめる」役割だけを担います。実装の手順そのものは WORKFLOW.md に従い、二重に定義しません。

## 振る舞い

### 対象のリポジトリ

- WORKFLOW.md の front matter にある `tracker.provider.repo` を対象にする。
- GitHub への操作は、すべて対象のリポジトリを明示して行う（`gh ... -R <owner/repo>`）。フォーク元のリポジトリには、読み取りを含め一切の操作をしない。
- WORKFLOW.md の手順は、git の `origin` に対して fetch と push を行う。`origin` が対象のリポジトリを指していないときは、fetch も push もせず、何も変更せずに終了する。

### Issue の選び方

- 対象は、open で、`symphony` ラベルが付いた Issue だけ。
- `sdd:*` ラベルによって、次の優先順で 1 件選ぶ。同じ順位の中では、番号の小さいものを先にする。

  | 優先 | ラベル | 理由 |
  |---|---|---|
  | 1 | `sdd:merging` | 人間が受け入れた作業を完了させる |
  | 2 | `sdd:rework` | 人間が差し戻した作業をやり直す |
  | 3 | `sdd:in-progress` | 途中の作業を続ける |
  | 4 | `sdd:todo` | 新しい作業に着手する |

- `sdd:backlog`、`sdd:human-review`、`symphony` ラベルの無い Issue には、コメント・ラベル変更を含め一切の変更を加えない（規則 R-6）。
- 対象が 1 件も無いときは、何も変更せずに終了する。

### 1 回の実行の範囲

- 1 回の `/sdd-run` で扱う Issue は 1 件。
- 選んだ Issue について、WORKFLOW.md の Step 0（状態の判定）から、その状態で進められるところまで進める。
- 引数に Issue 番号を渡した場合は、その Issue だけを対象にする。その Issue が対象の条件（open、`symphony` ラベル、上の表のラベル）を満たさないときは、何も変更せずに終了する。

### WORKFLOW.md の読み替え

WORKFLOW.md のプロンプト本文は、Symphony のランナーが値を埋めるテンプレートです。`/sdd-run` は次のように読み替えます。

| WORKFLOW.md の記述 | 読み替え |
|---|---|
| `{{ issue.identifier }}`、`{{ issue.title }}` など | `gh issue view` で取得した値 |
| `{% if attempt %}` の継続コンテキスト | 選んだ Issue が `sdd:in-progress` のときに当てはまるものとして扱う |
| `github_api` ツール | `gh` CLI（対象のリポジトリを明示） |
| 作業ディレクトリ（`workspace.root`、`hooks`） | Issue ごとの git worktree |

### 作業場所

- Issue ごとに専用の git worktree を作り、その中で作業する。
- `/sdd-run` を起動した作業ツリーにある、未コミットの変更や未追跡のファイルには触れない。

### 無人での実行

- 実行の途中で、人間に質問や確認を求めない。
- 進められなくなった場合（必要な認証・権限・ツールが無い、push できない、規範に反する作業が必要、など）は、理由を Workpad に記録し、ラベルを `sdd:human-review` に変えて終了する。
- Issue を選ぶ前に進められなくなった場合（対象のリポジトリを読み取れない、`origin` が対象のリポジトリを指していない）と、Workpad に書き込めない場合は、何も変更せずに終了し、理由を報告する。
- 終了時の報告には、完了した作業とブロッカーだけを書く（慣習 C-8）。

### 行動規範

- 行動規範（AGENTS.md と WORKFLOW.md に同期された `ethics/` の条文）が、`/sdd-run` と WORKFLOW.md の手順よりも優先する。

## 前提条件

| 条件 | 理由 |
|---|---|
| `gh` が対象のリポジトリに認証済みで、Issue・ラベル・Pull Request を操作できる | Issue の取得、ラベルの変更、Pull Request の作成に使う |
| git の `origin` が対象のリポジトリを指している | WORKFLOW.md の手順は、`origin` に対して fetch と push を行う |
| `git push` が、パスフレーズの入力などの対話なしで通る | 無人の実行では入力に応えられない |
| `sdd:*` と `symphony` のラベルが作成済み | 工程の進行をラベルで表す |
| Claude Code の権限設定が、`gh` と `git` の実行を確認なしで許可している | 確認の待ちでループが止まる |

## 受入条件

- [ ] 対象の Issue が無いとき、`/sdd-run` は Issue・ブランチ・ファイルを何も変更せずに終了する
- [ ] `sdd:todo` と `symphony` の付いた Issue が 1 件あるとき、`/sdd-run` はそれを `sdd:in-progress` に変え、Workpad を作り、実装して Pull Request を作り、`sdd:human-review` に変える
- [ ] `sdd:backlog` の Issue、`symphony` ラベルの無い Issue には、何の変更も加わらない
- [ ] 起動した作業ツリーの未コミットの変更と未追跡のファイルが、実行の前後で変わらない
- [ ] `/loop 10m /sdd-run` で、繰り返し実行できる
- [ ] `/sdd-run` が作る Pull Request は、`symphony` ラベルと `symphony/` で始まるブランチ名を持ち、規則 R-4 と R-5 の検査に合格する

## 対象外

- 複数の Issue の並列実行（WORKFLOW.md の `max_concurrent_agents` に相当するもの）
- Claude Code を起動していない間も動き続ける常駐の仕組み
- Symphony のランナーそのものの構築

## 未確定の点

- `/sdd-run` の定義ファイル自体を、規則 R-5 の保護対象に加えるかどうか。加えない場合、エージェントの Pull Request が、自分を起動する手順を書き換えられる。
