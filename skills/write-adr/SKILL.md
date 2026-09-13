---
name: write-adr
description: ADRを作成・更新し、テンプレート・状態・提案滞留を検証・整形する。
---

# ADR

`<tool>` はこのskillの `scripts/adr.py`（読まずに実行）。保存先は指定優先、なければ `docs/adr`。既存ADRは関連する決定だけ読む。

1. `python3 <tool> new --directory <保存先> --slug <英小文字短名> --title '<題名>'`
2. 出力のcontextに背景・制約・代替案、decisionに提案と理由、consequencesに利点・欠点・対応をユーザーの言語で記す。
3. `python3 <tool> format <変更ファイル>` で整形・検証。全件は `lint <保存先>`。

Proposed-onは提案開始日。既定30日以上のProposedは報告し、日付・状態の変更で隠さない。閾値指定は `--max-proposed-days N`。

状態変更・詳細仕様は [format.md](references/format.md)。別形式を無断変換しない。形式の根拠は必要時のみ [research.md](references/research.md) を読む。
