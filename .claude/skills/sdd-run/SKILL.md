---
description: Issue 駆動のサイクルを 1 周だけ進める。着手できる Issue を 1 件選び、WORKFLOW.md の手順をその Issue について実行する。利用者が /sdd-run と入力したとき、または /loop から呼ばれたときにだけ使う。
argument-hint: "[Issue番号]"
---

# /sdd-run：Issue 駆動のサイクルを 1 周進める

仕様: `docs/specs/claude-code-loop.md`

あなたは、Symphony のランナーの代わりに「Issue を 1 件選び、`WORKFLOW.md` の手順をその Issue について進める」役割を担います。実装の手順そのものは `WORKFLOW.md` のプロンプト本文に書かれています。ここに書かれているのは、Issue の選び方と、`WORKFLOW.md` の読み替えだけです。

引数: `$ARGUMENTS`（Issue 番号。空なら自動で選ぶ）

## 守ること

- **行動規範が最優先です。** `AGENTS.md` と `WORKFLOW.md` にある行動規範（`ethics/` の条文）は、このファイルと `WORKFLOW.md` の手順よりも優先します。
- **これは無人の実行です。** 途中で人間に質問や確認を求めないでください。進められなくなったら、下の「進められないとき」に従って終了します。
- **1 回の実行で扱う Issue は 1 件です。** 終わったら、他の Issue に進まずに終了します。
- **対象のリポジトリ以外に触れません。** GitHub への操作は、すべて `-R <対象のリポジトリ>` を付けて行います。フォーク元のリポジトリには、読み取りを含め一切の操作をしません。

## 手順

### 1. 対象のリポジトリを決める

`WORKFLOW.md` の front matter にある `tracker.provider.repo` を読みます。

```bash
REPO=$(sed -n '/^---$/,/^---$/p' WORKFLOW.md | grep -m1 'repo:' | sed 's/.*repo:[[:space:]]*//; s/[[:space:]]*#.*//')
echo "$REPO"
```

値を読み取れない場合は、何も変更せずに終了し、その旨を報告します。

### 2. Issue を 1 件選ぶ

open で `symphony` ラベルの付いた Issue を取得します。

```bash
gh issue list -R "$REPO" --state open --label symphony --limit 100 --json number,title,labels
```

次の優先順で 1 件選びます。同じ順位の中では、番号の小さいものを先にします。

| 優先 | ラベル |
|---|---|
| 1 | `sdd:merging` |
| 2 | `sdd:rework` |
| 3 | `sdd:in-progress` |
| 4 | `sdd:todo` |

- `sdd:backlog`、`sdd:human-review` の Issue と、`symphony` ラベルの無い Issue は対象外です。コメント・ラベル変更を含め、一切の変更を加えません（規則 R-6）。
- 引数に Issue 番号がある場合は、その Issue だけを見ます。open であること、`symphony` ラベルがあること、上の表のラベルのいずれかを持つことを確かめ、満たさなければ何も変更せずに終了します。
- **対象が 1 件も無いときは、何も変更せずに終了します。** 報告は「対象の Issue なし」の 1 行で十分です。

### 3. 作業場所を用意する

Issue ごとに専用の git worktree を作り、その中で作業します。場所は `WORKFLOW.md` の `workspace.root` の下にします。

```bash
git fetch origin main
git worktree list
```

- その Issue の worktree が既にあれば、それを使って続きから進めます。
- 無ければ、`origin/main` から新しく作ります。ブランチ名は `WORKFLOW.md` の規定（`symphony/<Issue番号>-<短い英語slug>`）に従います。
- **この実行を起動した作業ツリーにある、未コミットの変更や未追跡のファイルには触れません。** ブランチの切り替えも、起動した作業ツリーでは行いません。

### 4. WORKFLOW.md の手順を実行する

`WORKFLOW.md` の front matter より後ろ（プロンプト本文）を読み、選んだ Issue について Step 0 から実行します。本文は Symphony のランナーが値を埋めるテンプレートなので、次のように読み替えます。

| `WORKFLOW.md` の記述 | 読み替え |
|---|---|
| `{{ issue.identifier }}` | Issue 番号 |
| `{{ issue.title }}`、`{{ issue.state }}`、`{{ issue.labels }}`、`{{ issue.url }}`、`{{ issue.description }}` | `gh issue view <番号> -R "$REPO" --json title,state,labels,url,body` の値 |
| `{% if attempt %}` の継続コンテキスト | 選んだ Issue が `sdd:in-progress` のときに当てはまる |
| `github_api` ツール | `gh` CLI（`-R "$REPO"` を付ける） |
| 提供されたリポジトリコピー | 手順 3 で用意した worktree |

### 5. 終了する

- 選んだ Issue を、その状態で進められるところまで進めたら終了します。
- 最後の報告には、完了した作業とブロッカーだけを書きます（慣習 C-8）。扱った Issue の番号と、終了時のラベルを含めてください。

## 進められないとき

次のような場合は、それ以上進めません。

- 必要な認証・権限・ツールが無い
- `git push` が通らない（パスフレーズの入力を求められる場合を含む）
- 行動規範に反する作業が必要になった
- Issue の「関連する仕様」を特定できない（規則 R-7）

このときは、理由を Issue の Workpad に記録し、ラベルを `sdd:human-review` に変えて終了します。Workpad に書き込むこともできない場合は、何も変更せずに終了し、理由を報告します。
