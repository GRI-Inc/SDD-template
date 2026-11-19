---
tier: rule
---

<!--
重要：
このファイルは規則層です。エージェントはこのファイルを変更してはいけません。
改正は Pull Request のレビューを通して行います。
-->

# 規則（仕様駆動開発）

Issue 駆動で動くエージェントが、Issue と Pull Request を扱うときの規則です。
適用点 `pr` で `検査: deterministic` の規則は、CI が Pull Request ごとに自動で検査します。

## R-4 Pull Request は根拠となる仕様・仕様差分・Issue を明示する

- 強度: MUST
- 根拠: P-4, P-5
- 適用点: pr
- 検査: deterministic guards/pr_contract.py
- 違反時: block

Pull Request の本文には、根拠となる仕様 Markdown への相対リンク、仕様を変更したかどうか（変更していない場合は「変更なし」）、対応する Issue（`Fixes #番号`）を書く。

### 適合例

- `## 関連する仕様` に仕様への相対リンク、`## 仕様差分` に「変更なし」、`## 関連 Issue` に `Fixes #12` を書く。

### 違反例

- 仕様へのリンクを書かずに Pull Request を作る。
- `## 仕様差分` を空のままにする。

## R-5 エージェントの Pull Request で規範・憲章・執行の仕組みを変更しない

- 強度: MUST NOT
- 根拠: P-7
- 適用点: pr
- 検査: deterministic guards/protected_paths.py
- 違反時: block

エージェントが作る Pull Request に、理念・原則・規則の条文、ガード、`ethic_layer/`、プロジェクト憲章、`WORKFLOW.md`、CI の定義の変更を含めてはならない。変更が必要だと考えた場合は、`sdd:backlog` の Issue として起票する。

### 適合例

- 規則の見直しが必要だと考え、理由を書いた `sdd:backlog` の Issue を起票する。

### 違反例

- テストを通すために `ethics/20-rules/` の条文を書き換える。
- CI が失敗するので `.github/workflows/` の検査を外す。

## R-6 承認されていない Issue に着手しない

- 強度: MUST NOT
- 根拠: P-6
- 適用点: input
- 検査: judge
- 違反時: block

`sdd:backlog` の Issue と、`symphony` ラベルの無い Issue には、コメント・ラベル変更・実装を含め一切の変更を加えない。

### 適合例

- 担当の Issue が `sdd:backlog` だったので、何もせず終了する。

### 違反例

- 関連しそうだという理由で、`sdd:backlog` の Issue にコメントを書き込む。

## R-7 根拠となる仕様を特定できない Issue は実装しない

- 強度: MUST NOT
- 根拠: P-4
- 適用点: output
- 検査: judge
- 違反時: escalate

Issue の「関連する仕様」のリンクが無い、または壊れている場合は、実装せずにブロッカーとして記録し、人間の判断に委ねる。

### 適合例

- リンク先の仕様が存在しないことを Workpad に記録し、`sdd:human-review` に送る。

### 違反例

- リンクが壊れているので、Issue の題名から要件を推測して実装する。

## R-8 受入条件と検証をすべて満たすまで人間のレビューへ進めない

- 強度: MUST NOT
- 根拠: P-3
- 適用点: output
- 検査: judge
- 違反時: refine

Issue の「受入条件」「Validation」に未達の項目が残っている状態で、`sdd:human-review` に変えてはならない。外部要因で進められない場合は、ブロッカーであることを明記して送る。

### 適合例

- 受入条件をすべて確認し、実行したコマンドと結果を Workpad に記録してから `sdd:human-review` に変える。

### 違反例

- 検証コマンドを実行せずに、受入条件にチェックを入れて `sdd:human-review` に変える。

## R-9 仕様に無い改善は別の Issue として起票し、同じ Pull Request に含めない

- 強度: MUST
- 根拠: P-4
- 適用点: pr
- 検査: judge
- 違反時: refine

担当の Issue の範囲を超える改善を見つけた場合は、目的・受入条件・現在の Issue への参照を書いた `sdd:backlog` の Issue を起票する。

### 適合例

- 実装中に見つけた別箇所の不具合を、`sdd:backlog` の Issue として起票する。

### 違反例

- 担当の Issue と関係のないリファクタリングを、同じ Pull Request に含める。

## R-10 Issue の本文を書き換えない

- 強度: MUST NOT
- 根拠: P-6
- 適用点: tool_call
- 検査: judge
- 違反時: block

Issue の本文は、人間が承認した受入の入力である。計画や進捗の記録のために書き換えてはならない。

### 適合例

- 計画と進捗を、Issue のコメントとして作った Workpad に書く。

### 違反例

- 受入条件を満たせないので、Issue の本文から該当の項目を削除する。
