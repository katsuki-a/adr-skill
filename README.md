# ADR Skill

ADR（Architecture Decision Record）を小さなテンプレートで作成し、形式・状態・Proposedの滞留を検証するCodex skill。Python 3.9以上の標準ライブラリだけで動く。通常実行にはパッケージ導入・ネットワーク・LLMによる全文検査を必要としない。

[Nygard](https://www.cognitect.com/blog/2011/11/15/documenting-architecture-decisions)、[MADR 4.0.0](https://github.com/adr/madr/blob/4.0.0/template/adr-template.md)、[ADR形式の公式紹介](https://adr.github.io/adr-templates/)を調査し、Nygardの構成を基にした独自の軽量プロファイルを採用した。開発時の[調査と選定理由](docs/adr-format-research.md)は配布するskillの外に保存している。

## 使う

`skills/write-adr` をCodexのskillディレクトリに配置する。ローカル開発では、このリポジトリを参照するシンボリックリンクで利用できる。既存の同名skillがある場合は上書きせず設置先を調整する。

```sh
mkdir -p "${CODEX_HOME:-$HOME/.codex}/skills"
ln -s "$PWD/skills/write-adr" "${CODEX_HOME:-$HOME/.codex}/skills/write-adr"
```

Codexで `$write-adr` を指定するか、ADR作成を依頼する。skillが読み込まれたら、生成ツールで採番し、出力された雛形を埋め、整形・検証をまとめて実行する。[SKILL.md](skills/write-adr/SKILL.md)には通常作業に必要な短い指示だけを置き、詳細仕様は必要時だけ読む。

CLI単体でも利用可能。以下はリポジトリのルートで実行する例。

```sh
python3 skills/write-adr/scripts/adr.py new --directory docs/adr --slug use-sqlite --title 'SQLiteを採用する'
# 生成されたADRの本文プレースホルダーを埋める
python3 skills/write-adr/scripts/adr.py format docs/adr/ADR-001-use-sqlite.md
python3 skills/write-adr/scripts/adr.py lint docs/adr
python3 skills/write-adr/scripts/adr.py format docs/adr --check
```

## 採番と一覧

識別子は `ADR-001`、ファイル名は `ADR-001-slug.md`、見出しは `# ADR-001: Title`。番号は最低3桁で、999の次はADR-1000となる。

`new` と `format` は同じディレクトリのREADMEに、ID・タイトル・状態・提案日・置換先の一覧表を自動生成・更新する。[このリポジトリのADR一覧](docs/adr/README.md)もこの機能で生成している。READMEの管理領域の外にある説明は保持する。

```sh
python3 skills/write-adr/scripts/adr.py index docs/adr
python3 skills/write-adr/scripts/adr.py index docs/adr --check
```

手動でADRを変更・改名・削除した後はindexで更新する。`index --check` は一覧が古い場合に失敗する。`format --check` はADRと一覧を両方確認する。lint単体では一覧の同期は検査しない。自動更新はCLI実行時であり、バックグラウンド監視ではない。

## 検証と整形

状態・提案開始日・置換先は、ファイル先頭の限定YAMLフロントマターに記録する。[配置と構文の決定を記録したADR](docs/adr/ADR-001-use-front-matter-for-adr-metadata.md)も、このskillで生成・検証している。

Context内の英語見出し `Problem to Solve` と `Considered Options and Trade-offs` に、課題・判断軸と各案の比較を分けて記録する。Decisionには選択と理由、Consequencesには採用後の影響を記す。

- ファイル名・番号、H1/H2の構成と順序、必須メタデータ、空の節、雛形の未記入を検出。
- 状態は `Proposed / Accepted / Rejected / Deprecated / Superseded` の5種類。Supersededには実在する別ADRファイルへの `superseded-by` が必要。
- `proposed-on` が実在する日付か、未来でないかを検証。Proposedは提案開始から**30暦日以上**でエラー。`--max-proposed-days N` で変更できる。
- formatterはLF改行、構造見出し、フロントマターのキー順・日付の引用符、節境界の空行を統一する。本文のハード改行・コード・空白はLF化以外を保持する。意味上のエラーがあるファイルは変更しない。

判定は記録された日付と現在の状態に基づく。Gitの遷移履歴、実際の合意、提案日の改ざん、判断の妥当性は検証しない。対応YAMLは3つのキーと単純な文字列に限定し、コメント・配列・ネストなどは拒否する。旧Status節は自動変換せず、明示的な移行が必要。別のADR形式を汎用的に整形するツールではない。[対応形式とCLI仕様](skills/write-adr/references/format.md)に境界と終了コードを記載している。

滞留検出は実行時に行う。無変更のADRを継続的に確認する場合は、CIなどから全件lintを定期実行する。このリポジトリはスケジューラや自動通知を含まない。

## 速度とLLM入力コスト

[測定結果](reports/benchmark.json)（2026-09-14、macOS arm64、Python 3.9.6、7回の中央値）。毎回Pythonプロセスを新規起動し、OSのファイルキャッシュは消去していない。

| 処理 | 中央値 |
| --- | ---: |
| 1 ADRのlint | 33.8 ms |
| 100 ADRのlint | 46.4 ms |
| 1,000 ADRのlint | 137.6 ms |
| 新規雛形の生成 | 33.8 ms |
| 1 ADRの整形＋lint | 34.4 ms |
| 1,000 ADRの一覧生成・同期 | 80.4 ms |
| 1 ADRの整形＋同じディレクトリの1,000件の一覧同期 | 80.6 ms |

一覧計測は初回の生成と生成済み一覧の照合を含む。件数ごとの揺らぎには実行時の負荷が影響する。

正常出力は1行（1,000件でも38 bytes）、エラーは既定20件まで。lintは変更ファイルだけを検査できる。formatは一覧更新のため同じディレクトリの各ADRの先頭も読むが、表をLLMには出力しない。文書をキャッシュしないため、前回の結果を再利用して提案の経過日数を見落とすこともない。

`o200k_base`による入力量の参考値では、skill本文382 tokens、生成された雛形等75、検証結果13、コマンド文字列39、計509 tokens。共通の判断材料と完成ADRは両方式から除外した。

| 既存ADRを直接読む比較例 | 1件 | 3件 | 10件 |
| --- | ---: | ---: | ---: |
| 短いADRの例 | 82 | 246 | 820 |
| 同梱の比較用ADR | 392 | 1,176 | 3,920 |

これは**実課金やLLMの品質・所要時間を測るA/Bテストではない**。実際のモデルのtokenizer、ツール呼び出しの包み、長いパス、キャッシュ割引、修正の往復は含まない。短いADRが1件だけ、または既にコンテキストにある場合には、skillを使う方が高コストになる可能性がある。あらゆる場合のコスト逆転防止は保証できない。

固定の入力負担を小さくし、既存ADRの形式を真似るための読み込みと再検証を省く設計にしている。比較用ADRを複数読むケースでは入力を削減でき、決定論的な形式・期限検査をLLMなしで行える。

## 開発時の検証

```sh
python3 -B -m unittest discover -s tests -v
python3 skills/write-adr/scripts/adr.py lint tests/fixtures docs/adr --today 2026-09-13
python3 skills/write-adr/scripts/adr.py index docs/adr --check
python3 tools/benchmark.py
```

`tests/fixtures` はテスト・比較用の架空のADRであり、このプロジェクトで実際に承認された記録ではない。テストは日付を固定し、期限の境界、日付、状態、整形の冪等性、本文保持、非対応構文、出力上限などを検証する。

ベンチマークは標準ライブラリだけで速度を測定できる。任意の検証用環境に `tiktoken` がある場合だけトークン比較も出力する（辞書の初回取得には通信が必要な場合がある）。skillの実行依存には含めない。Codexの `skill-creator/scripts/quick_validate.py` によるメタデータ検証も実施済み。こちらのPyYAMLも開発時の検証環境だけに用いた。
