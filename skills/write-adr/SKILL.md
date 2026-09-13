---
name: write-adr
description: ADRを作成・更新し、テンプレート・状態・提案滞留を検証・整形する。
---

# ADR

`<tool>` はこのskillの `scripts/adr.py`（読まずに実行）。保存先は指定優先、なければ `docs/adr`。既存ADRは関連する決定だけ読む。

1. `python3 <tool> new --directory <保存先> --slug <英小文字短名> --title '<題名>'`
2. 出力のproblemに解決したい課題・制約・判断軸、optionsに各選択肢の利点・欠点・受け入れる制約、decisionに選択と理由、consequencesに採用後の影響・対応をユーザーの言語で記す。
3. `python3 <tool> format <変更ファイル>` で整形・検証。全件は `lint <保存先>`。new/formatは同じ保存先のREADME一覧も更新する。

フロントマターのproposed-onは提案開始日。既定30日以上のProposedは報告し、日付・状態の変更で隠さない。閾値指定は `--max-proposed-days N`。

状態変更・詳細仕様は [format.md](references/format.md)。別形式を無断変換しない。

識別子は `ADR-001`、見出しは `# ADR-001: Title`。手動編集・改名・削除後の一覧更新は `python3 <tool> index <保存先>`、更新漏れの検査は同コマンドに `--check`。
