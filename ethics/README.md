# 倫理階層（ethics/）

AI エージェントに守らせる規範を、効力の強さで 4 層に分けて Markdown で管理します。
上位の層が下位の層を支配する関係を、lint で機械的に保ちます。

このリポジトリでは、Issue 駆動で動くエージェントの行動規範そのものです。**ここに条文を追記すれば、エージェントはその規範に従って動くようになります。** 運用の全体像は [Issue 駆動開発ガイド](../docs/guides/issue-driven-sdd.md) を参照してください。

```bash
python3 -m ethic_layer lint ethics --strict --tree   # 構造を検査する
python3 -m ethic_layer sync                          # WORKFLOW.md のプロンプトへ反映する
```

## 階層

| 層 | tier | ID | 答える問い | 改正 | 逸脱 |
|---|---|---|---|---|---|
| 理念 | `ideal` | `I-n` | 何のためか | 最高責任者のみ | 不可 |
| 原則 | `principle` | `P-n` | どう判断するか | 人間のレビュー必須 | 不可 |
| 規則 | `rule` | `R-n` | 何をする・しないか | Pull Request のレビュー | `例外` に明記した場合のみ |
| 慣習 | `custom` | `C-n` | 普段どうするか | チームの裁量 | 理由を示せば可 |

強さには 2 つの軸があります。

- **効力**: 理念 > 原則 > 規則 > 慣習。衝突したときは上位の層が勝ちます。
- **検査可能性**: 規則が最も高く、理念は抽象的なので直接は検査しません。

そのため「絶対に守らせたいこと」は、理念として宣言したうえで、必ず規則まで具体化します。
理念を書いただけでは守られません。

## ディレクトリ構成

```
ethics/
  00-ideals.md        理念（1 ファイル）
  10-principles/      原則
  20-rules/           規則
  30-customs/         慣習
  guards/             規則を決定的に検査するコード
```

各層のファイルは分野ごとに分割してかまいません。ID は ethics/ 全体で一意にします。

## 条文の書き方

ファイルの先頭に `tier` を書き、条文は `## <ID> <題名>` の見出しで始めます。
見出しの直後に箇条書きでフィールドを並べ、空行のあとに本文を書きます。

```markdown
---
tier: rule
---

## R-1 個人情報を組織外の宛先へ送信しない

- 強度: MUST NOT
- 根拠: P-1
- 適用点: tool_call
- 検査: deterministic guards/pii_egress.py
- 違反時: block

本文。

### 適合例

### 違反例
```

### フィールド

| フィールド | 理念 | 原則 | 規則 | 慣習 | 値 |
|---|---|---|---|---|---|
| 強度 | — | 必須 | 必須 | 必須 | 原則・規則: `MUST` / `MUST NOT`、慣習: `SHOULD` / `SHOULD NOT` / `MAY` |
| 根拠 | — | 必須 | 必須 | 必須 | 上位層の条文 ID。複数ならカンマ区切り |
| 検査 | — | 必須 | 必須 | 任意 | `judge`（LLM 判定器）または `deterministic <ガードのパス>` |
| 適用点 | — | — | 必須 | — | `input` / `plan` / `tool_call` / `output` / `pr`。複数ならカンマ区切り |
| 違反時 | — | — | 必須 | — | `block`（止める）/ `refine`（再生成）/ `escalate`（人に委ねる） |
| 例外 | — | — | 任意 | — | 逸脱を認める条件 |

規則の `### 適合例` と `### 違反例` は、判定器の評価やプロンプト最適化の訓練例として使うことを想定しています。

## 支配構造を保つ原則

1. **上位優先**: 衝突したときは上位の層が勝つ。同じ層の中では、個別の条文が一般の条文に、新しい条文が古い条文に優先する。
2. **根拠必須**: 原則・規則・慣習は、上位層の条文を `根拠` に持つ。根拠のない条文は無効。
3. **具体化のみ**: 下位の条文は上位を具体化する。厳しくすることはできるが、緩めることはできない。
4. **欠缺補充**: 規則が沈黙する場面では原則に、原則も沈黙する場面では理念に遡って判断する。
5. **昇格**: 繰り返し守られた慣習や、破られて実害が出た慣習は、規則として成文化する。
6. **執行可能性**: すべての理念は、検査できる規則を少なくとも 1 つ子孫に持つ。
7. **硬性**: 上位の層ほど改正を難しくする。エージェントは理念・原則・規則を書き換えない。

## lint

```bash
python3 -m ethic_layer lint ethics --strict --tree
```

`.github/scripts/lint_ethics.py` も同じ検査を実行します。

- `--strict`: 警告もエラーとして扱います（CI ではこの設定）。
- `--tree`: 根拠のつながりを木で表示します。

| コード | 内容 | 対応する原則 |
|---|---|---|
| E001–E005 | tier・置き場所・見出し・ID の形式と重複 | — |
| E006–E008 | 必須フィールドの欠落、その層で使えないフィールド、不正な値 | — |
| E009 | 根拠が未定義の ID を指している | 根拠必須 |
| E010 | 根拠が上位層の条文でない | 上位優先 |
| E011 | `deterministic` と宣言したガードのファイルが無い | 執行可能性 |
| E012–E013 | 本文が無い、条文が 1 つも無い | — |
| W001 | 理念を具体化する規則が無い | 執行可能性 |
| W002 | 理念が 7 個を超えている | — |
| W003 | 規則に適合例・違反例が無い | — |

### lint が検査しないこと

- **意味の矛盾**: 下位の条文が上位の条文を緩めていないか（原則 3）は、文章の意味の判定が必要なため検査しません。レビューで確認してください。
- **改正の権限**: 層ごとの承認者（原則 7）は、CODEOWNERS やブランチ保護で設定してください。
- **実行時の遵守**: この lint は条文の構造を検査するもので、エージェントが実際に条文を守ったかどうかは検査しません。

## コンパイル

`ethic_layer/` は、lint に合格した条文集を実行時の成果物へ変換します。lint でエラーが出る条文集はコンパイルできません。

```bash
python3 -m ethic_layer compile ethics
```

| 成果物 | 取得方法 | 用途 |
|---|---|---|
| 条文集プロンプト | `compiled.prompt()` | 理念・原則・規則。凍結して入力の値として渡す |
| 慣習の指示文 | `compiled.customs_prompt()` | 最適化してよい指示文の初期値 |
| ガード登録表 | `compiled.guards(point)` | 適用点ごとの決定的ガード |
| 判定対象の一覧 | `compiled.judged(point)` | 適用点ごとの、LLM 判定器にかける条文 |
| 版の識別子 | `compiled.digest` | どの版の規範が効いていたかの記録 |

`--json PATH` を付けると、条文の登録表を JSON で書き出します。ここまでは標準ライブラリだけで動きます。

### ガードの契約

`検査: deterministic <パス>` で指すファイルには、次の関数を定義します。違反の説明を返し、空リストなら適合です。

```python
def guard(event: dict) -> list[str]: ...
```

| 適用点 | event |
|---|---|
| `tool_call` | `{"point", "tool": ツール名, "args": 引数の辞書}` |
| `input` | `{"point", "inputs": 入力の辞書, "text": 入力を文字列にしたもの}` |
| `output` | `{"point", "outputs": 出力の辞書, "text": 出力を文字列にしたもの}` |
| `pr` | `{"point", "files": 変更されたパスの一覧, "body": 本文, "labels": ラベルの一覧, "head": ブランチ名, "title": 題名}` |

ガードが例外を出した場合は、素通りさせず違反として扱います。

## Issue 駆動のエージェントへの接続

Issue 駆動で動くエージェント（Symphony など）には、次の 2 つの経路で規範を届けます。

### プロンプトへの注入

```bash
python3 -m ethic_layer sync            # WORKFLOW.md を更新する
python3 -m ethic_layer sync --check    # 反映漏れがあれば失敗する（CI 用）
```

`WORKFLOW.md` の `<!-- ethics:begin -->` と `<!-- ethics:end -->` の間を、4 層すべての条文集で置き換えます。末尾には規範の版（digest）が入り、エージェントはそれを Workpad に記録します。この区間は生成物なので、手で編集しないでください。

### Pull Request の自動検査

```bash
python3 -m ethic_layer check-pr ethics --files-from files.txt --body-file body.md --labels symphony --head symphony/12-fix
```

`適用点: pr` かつ `検査: deterministic` の規則を実行します。CI では [ethics-pr-guard](../.github/workflows/ethics-pr-guard.yml) が Pull Request ごとに実行します。規則とガードを追加すれば、CI の定義を変えずに検査が増えます。

CI は base ブランチ側の条文とガードで検査します。Pull Request が、自分を検査するガードを書き換えても効きません。

`適用点: pr` でも `検査: judge` の規則は自動では検査されません。プロンプトで伝えたうえで、人間のレビューで確認します。

## DSPy との接続

DSPy で組んだプログラムに規範を守らせる場合の接続です。Issue 駆動のエージェント（Symphony から起動するコーディングエージェント）はこの経路を通りません。

`ethic_layer/dspy_adapter.py` が、コンパイル結果を DSPy のプログラムに接続します（DSPy 3.5.0 で動作確認）。

```python
import dspy
from ethic_layer import compile_ethics
from ethic_layer.dspy_adapter import Governed, Judge, guard_tools, make_metric, with_ethics

compiled = compile_ethics("ethics")

agent = Governed(
    dspy.ReAct(with_ethics(MySignature, compiled), tools=guard_tools(my_tools, compiled)),
    compiled,
)

metric = make_metric(compiled, my_task_metric, judge=Judge(lm=judge_lm))
optimized = dspy.GEPA(metric=metric, auto="light", reflection_lm=reflection_lm).compile(agent, trainset=trainset)
```

| 部品 | 役割 |
|---|---|
| `with_ethics` | 規範を受け取る入力フィールドを足す。慣習は指示文に追記する |
| `guard_tools` | ツール呼び出しの直前に決定的ガードを実行し、違反した呼び出しは実行しない |
| `Governed` | 規範の注入、入出力のガード、ツール呼び出しの記録（`pred.ethics_log`） |
| `Judge` | `検査: judge` の条文を LLM で判定する。エージェントとは別のモデルを指定できる |
| `make_metric` | 規範のゲートを付けた metric を作る |

### 規範を最適化から守る仕組み

- 理念・原則・規則は**入力フィールドの値**として渡します。プロンプト最適化が書き換えるのは指示文と例示で、入力の値は書き換えないため、規範は最適化の対象になりません。
- 慣習だけは指示文に追記します。最適化器が書き換えてよい層です。
- metric は**辞書式**に評価します。理念・原則・規則の違反が 1 つでもあればスコアは 0 で、タスクの出来は見ません。違反が無いときだけタスクのスコアを使い、慣習の違反は 1 件ごとに減点します。
- ガードに阻止されたツール呼び出しも違反として数えます。「試みたが止められた」振る舞いを最適化で減らすためです。
- 違反のフィードバックには、条文 ID と理念までの根拠の系譜が入ります。

### 注意点

- `make_metric` の既定の戻り値は `dspy.Prediction(score, feedback)` です。`dspy.BootstrapFewShot` のように戻り値の真偽で例示を採否する最適化器では `feedback=False` を指定してください（Prediction はスコア 0 でも真になります）。
- `judge` を渡さない場合、`検査: judge` の条文は評価されません。
- 適用点 `tool_call` の判定器条文は、`Governed` が記録したツール呼び出しを**実行後に**評価します。実行前に止めるのは決定的ガードだけです。
- 適用点 `plan` の条文は、計画の表現が決まっていないため評価できません。
- 判定器は誤判定します。人手でラベルを付けた例で、判定器自体の精度を測ってください。

### テスト

```bash
python3 -m unittest discover -s ethic_layer/tests -t .
```

DSPy が入っていない環境では、アダプタのテストは飛ばされます。

## 同梱の条文について

| ファイル | 内容 |
|---|---|
| `*/core.md` と `guards/pii_egress.py` | 分野を問わない一般の規範。書き方の例を兼ねる |
| `*/sdd.md`、`guards/pr_contract.py`、`guards/protected_paths.py` | このリポジトリの Issue 駆動エージェントが従う、仕様駆動開発の規範 |

フォークして使う場合は、組織の規範に合わせて書き換えてください。`guards/protected_paths.py` の保護対象と、`guards/pii_egress.py` の組織内ドメインは、導入先に合わせた見直しが必要です。
