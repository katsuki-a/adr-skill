# ADR形式の調査

調査日: 2026-09-13。以下の一次資料を確認した。ADRには複数の形式があり、単一の必須標準として扱わない。

| 形式 | 主な構成 | 今回の用途との関係 |
| --- | --- | --- |
| Nygard | タイトル、状態、背景、決定、結果 | 小さい文書で判断と理由を残せる。今回の基本構成に採用。 |
| MADR 4.0.0 | 背景と問題、検討した選択肢、決定結果。詳細版には判断軸、選択肢ごとの比較や確認方法などもある | 比較を詳しく残したい場合に適する。今回は代替案をContextに簡潔に含める。 |
| Y-Statement | 背景・懸念・選択・期待品質・許容する欠点を短文で結ぶ | 最小の記録に向くが、今回求める状態と滞留検証にはメタデータの追加が必要。 |

Nygardは1つの重要な決定を短い文書にまとめ、置換前の決定も履歴として保存する考え方を示している。MADRにはminimal/bareもあり、MADRそのものが常に長いわけではない。

## このskillの独自プロファイル

Nygard由来の構成に、機械検証できる `status` と `proposed-on` をフロントマターに置く。状態はNygardとMADRを参考に5種類へ固定する。提案30日以上でエラー、日付の必須化、大文字小文字、見出し順序、置換先の別フィールド化は**このツールの運用規約**であり、ADR一般の標準ではない。MADR完全互換とは称さない。

proposed-onはファイルの更新日時と分離する。Git履歴走査は実行せず、記録された開始日を基準にする。本文の妥当性や合意の存在は人がレビューする。

## 一次資料

- Michael Nygard, [Documenting Architecture Decisions](https://www.cognitect.com/blog/2011/11/15/documenting-architecture-decisions), 2011-11-15。基本構成と短い記録、連番、置換後の履歴保存。原文はCC0。
- MADR project, [About MADR](https://adr.github.io/madr/)、[4.0.0 template](https://github.com/adr/madr/blob/4.0.0/template/adr-template.md)。固定版を比較対象とし、開発版とは区別。MITまたはCC0のデュアルライセンス。
- ADR GitHub organization, [ADR Templates](https://adr.github.io/adr-templates/)。Nygard、MADR、Y-Statement等の比較と一次資料への案内。

同梱テンプレートと説明文はこのプロファイル向けに記述しており、資料の全文を転載していない。

メタデータの配置には、MADRの [Use YAML front matter for metadata](https://adr.github.io/madr/decisions/0013-use-yaml-front-matter-for-meta-data.html) も参照した。本文との分離とツール連携に利点がある一方、表示互換性には限界がある。今回の具体的な構文は独自の限定プロファイルである。
