# ADR Skill

ADR（Architecture Decision Record）を小さなテンプレートで作成し、形式・状態・Proposedの滞留を検証するCodex skill。Python 3.9以上の標準ライブラリだけで動く。通常実行にはパッケージ導入・ネットワーク・LLMによる全文検査を必要としない。

[Nygard](https://www.cognitect.com/blog/2011/11/15/documenting-architecture-decisions)、[MADR 4.0.0](https://github.com/adr/madr/blob/4.0.0/template/adr-template.md)、[ADR形式の公式紹介](https://adr.github.io/adr-templates/)を調査し、Nygardの構成を基にした独自の軽量プロファイルを採用した。[調査と選定理由](skills/write-adr/references/research.md)を参照。

## 使う

`skills/write-adr` をCodexのskillディレクトリに配置する。ローカル開発では、このリポジトリを参照するシンボリックリンクで利用できる。既存の同名skillがある場合は上書きせず設置先を調整する。

```sh
mkdir -p "${CODEX_HOME:-$HOME/.codex}/skills"
ln -s "$PWD/skills/write-adr" "${CODEX_HOME:-$HOME/.codex}/skills/write-adr"
```

Codexで `$write-adr` を指定するか、ADR作成を依頼する。skillが読み込まれたら、生成ツールで採番し、出力された雛形を埋め、整形・検証をまとめて実行する。[SKILL.md](skills/write-adr/SKILL.md)には通常作業に必要な短い指示だけを置き、調査資料・詳細仕様は必要時だけ読む。

CLI単体でも利用可能。以下はリポジトリのルートで実行する例。

```sh
python3 skills/write-adr/scripts/adr.py new --directory docs/adr --slug use-sqlite --title 'SQLiteを採用する'
# 生成されたADRの本文プレースホルダーを埋める
python3 skills/write-adr/scripts/adr.py format docs/adr/0001-use-sqlite.md
python3 skills/write-adr/scripts/adr.py lint docs/adr
python3 skills/write-adr/scripts/adr.py format docs/adr --check
```

## 検証と整形

- ファイル名・番号、H1/H2の構成と順序、必須メタデータ、空の節、雛形の未記入を検出。
- 状態は `Proposed / Accepted / Rejected / Deprecated / Superseded` の5種類。Supersededには実在する別ADRファイルへの `Superseded-by` が必要。
- `Proposed-on` が実在する日付か、未来でないかを検証。Proposedは提案開始から**30暦日以上**でエラー。`--max-proposed-days N` で変更できる。
- formatterはLF改行、構造見出し、メタデータ、節境界の空行を統一する。本文のハード改行・コード・空白はLF化以外を保持する。意味上のエラーがあるファイルは変更しない。

判定は記録された日付と現在の状態に基づく。Gitの遷移履歴、実際の合意、提案日の改ざん、判断の妥当性は検証しない。別のADR形式を汎用的に整形するツールではない。[対応形式とCLI仕様](skills/write-adr/references/format.md)に境界と終了コードを記載している。

滞留検出は実行時に行う。無変更のADRを継続的に確認する場合は、CIなどから全件lintを定期実行する。このリポジトリはスケジューラや自動通知を含まない。

## 速度とLLM入力コスト

[測定結果](reports/benchmark.json)（2026-09-13、macOS arm64、Python 3.9.6、7回の中央値）。毎回Pythonプロセスを新規起動し、OSのファイルキャッシュは消去していない。

| 処理 | 中央値 |
| --- | ---: |
| 1 ADRのlint | 29.8 ms |
| 100 ADRのlint | 40.7 ms |
| 1,000 ADRのlint | 135.9 ms |
| 新規雛形の生成 | 30.3 ms |
| 1 ADRの整形＋lint | 30.2 ms |

正常出力は1行（1,000件でも38 bytes）、エラーは既定20件まで。通常は変更ファイルだけを検査する。文書をキャッシュしないため、前回の結果を再利用して提案の経過日数を見落とすこともない。

`o200k_base`による入力量の参考値では、skill本文289 tokens、生成された雛形等59、検証結果13、コマンド文字列38、計399 tokens。共通の判断材料と完成ADRは両方式から除外した。

| 既存ADRを直接読む比較例 | 1件 | 3件 | 10件 |
| --- | ---: | ---: | ---: |
| 短いADRの例 | 82 | 246 | 820 |
| 同梱の比較用ADR | 393 | 1,179 | 3,930 |

これは**実課金やLLMの品質・所要時間を測るA/Bテストではない**。実際のモデルのtokenizer、ツール呼び出しの包み、長いパス、キャッシュ割引、修正の往復は含まない。短いADRが1件だけ、または既にコンテキストにある場合には、skillを使う方が高コストになる可能性がある。あらゆる場合のコスト逆転防止は保証できない。

固定の入力負担を小さくし、既存ADRの形式を真似るための読み込みと再検証を省く設計にしている。比較用ADRを複数読むケースでは入力を削減でき、決定論的な形式・期限検査をLLMなしで行える。

## 開発時の検証

```sh
python3 -B -m unittest discover -s tests -v
python3 skills/write-adr/scripts/adr.py lint tests/fixtures --today 2026-09-13
python3 tools/benchmark.py
```

`tests/fixtures` はテスト・比較用の架空のADRであり、このプロジェクトで実際に承認された記録ではない。テストは日付を固定し、期限の境界、日付、状態、整形の冪等性、本文保持、非対応構文、出力上限などを検証する。

ベンチマークは標準ライブラリだけで速度を測定できる。任意の検証用環境に `tiktoken` がある場合だけトークン比較も出力する（辞書の初回取得には通信が必要な場合がある）。skillの実行依存には含めない。Codexの `skill-creator/scripts/quick_validate.py` によるメタデータ検証も実施済み。こちらのPyYAMLも開発時の検証環境だけに用いた。
