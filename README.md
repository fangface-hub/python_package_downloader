# pythonパッケージダウンローダー

このプロジェクトは、指定されたプラットフォームやPythonバージョンに対応したパッケージをダウンロードできるPythonパッケージダウンローダーです。さまざまな環境での依存関係管理を簡単にすることを目的としています。

## プロジェクト構成

```text
python_package_downloader
├── python_package_downloader.py   # アプリのエントリポイント
├── main_window.py                 # Tkinter GUI本体
├── python_package_utility.py      # ダウンロード処理と依存関係解析
├── requirements_editor.py         # パッケージリスト編集UI
├── i18n.py                        # 多言語化処理
├── pathlibex.py                   # パス/データディレクトリ管理
├── loggingex.py                   # ログ設定ユーティリティ
├── signalex.py                    # サブプロセス実行/シグナル制御
├── subprocessex.py                # ダウンロード監視・補助関数
├── tkinterex.py                   # カスタムTkinterウィジェット
├── treeviewex.py                  # TreeView拡張
├── config.json                    # Pythonバージョン/OSマッピング設定
├── loggingex_config.json          # ログ出力設定
├── pyproject.toml                 # プロジェクト設定
├── nuitka.cfg                     # Nuitka設定
├── build_nuitka.ps1               # EXEビルド
├── build_msix.ps1                 # MSIXビルド
├── build_and_package.ps1          # EXE/MSIXビルドと署名
├── bump_patch.ps1                 # バージョン更新
├── sign_code.ps1                  # 署名共通処理
├── sign_msix.ps1                  # MSIX署名
├── create_certificate.ps1         # 自己署名証明書作成
├── help/                          # ヘルプHTML
├── help_source/                   # ヘルプ原稿(Markdown)
├── locales/                       # 多言語辞書(JSON)
├── msix_build/                    # MSIX作業ディレクトリ
└── README.md                      # プロジェクトのドキュメント
```

## インストール

### 前提条件

[uv](https://docs.astral.sh/uv/) をインストールしてください。

### 仮想環境のセットアップ

1. プロジェクトディレクトリに移動して、uv を使用して依存関係をインストール:

```powershell
uv sync
```

これにより、`.venv` 仮想環境が自動作成され、すべての依存関係がインストールされます。

1. 仮想環境を有効化する (オプション):

```powershell
.\.venv\Scripts\Activate.ps1
```

**注:** uv を使用する場合、`pip install` 不要で、`uv sync` が自動的に仮想環境を作成・管理します。

## 使用方法

1. リポジトリをダウンロードして、python_package_downloader.py を実行する

1. ダウンロード情報を入力する

    画面項目は以下のとおり。

    | 画面項目 | 説明 |
    | ---- | ---- |
   | ダウンロード方法 | 必須項目<br>uvを使う： `uv pip download` で取得する<br>pipを使う： pip で `pip download` する<br>pipを使わない： PyPISimpleとrequestsで取得する |
    | OSを選択 | Windows,Linux,macOS を選択する |
    | Pythonバージョン | 必須項目,複数選択可<br>ターゲットのpythonバージョンを選択する |
    | パッケージリスト | 必須項目<br>パッケージリスト(テキストファイル)のパスを指定する<br>書式は `pip install -r requirements.txt` の `requirements.txt` と同じ |
    | ダウンロード先 | 必須項目<br>ダウンロード先のフォルダを指定する。<br>スクリプト格納場所の downloads が初期値 |
    | pipのパス | pipを使う場合必須項目<br>ダウンロード環境にある pip を探して初期表示する |
    | プロキシを使用する<br>ユーザ～ポート | 任意項目<br>プロキシを使う場合、入力する |
    | ソース形式を含める | 任意項目<br> ダウンロードできなかった場合、tar.gz形式のダウンロードを試みる |  
    | 依存関係をダウンロード | ダウンロードしたパッケージの依存関係を調べて再帰的にダウンロードする<br>パッケージに応じて所要時間が長くなるので注意 |

    > 「設定を保存」ボタンを押すと入力項目を保存する

1. 「ダウンロード開始」ボタンを押す

## ビルド方法

### ビルド前提条件

Nuitka でビルドするには、以下がインストールされている必要があります：

- **LLVM/Clang**: C/C++ コンパイラ（通常は Visual C++ Build Tools または LLVM をインストール）
- **Nuitka**: Python パッケージ（`uv sync --group build` でインストール）

### 開発用依存関係のインストール

Nuitka とビルド関連ツールをインストール：

```powershell
uv sync --group build
```

### EXE/MSIX をまとめてビルドする（推奨）

以下を実行すると、EXE と MSIX をビルドして署名まで行います。

```powershell
.\build_and_package.ps1
```

オプション：

```powershell
.\build_and_package.ps1 -ExeOnly
.\build_and_package.ps1 -MsixOnly
```

生成物：

- `dist/PythonPackageDownloader.exe`
- `dist/PythonPackageDownloader.msix`
- `dist/PythonPackageDownloader.cer`

### 個別ビルド

EXE のみビルド：

```powershell
.\build_nuitka.ps1
```

MSIX のみビルド（署名は別途）：

```powershell
.\build_msix.ps1
```

### ビルドのカスタマイズ

ビルド設定は以下のファイルで管理されます：

- [pyproject.toml](pyproject.toml) - `[tool.nuitka]` セクション
- [nuitka.cfg](nuitka.cfg) - Nuitka の詳細設定

または、`build_nuitka.ps1` / `build_and_package.ps1` を直接編集してカスタマイズできます。

## バージョン更新

`bump_patch.ps1` を使うと、以下の2ファイルのバージョンを同時に更新できます。

- `pyproject.toml` の `version` (`X.Y.Z`)
- `AppxManifest.xml` の `Version` (`X.Y.Z.0`)

### 使い方

パッチバージョンを1つ上げる（既定動作）:

```powershell
.\bump_patch.ps1
```

メジャー/マイナーバージョンを上げる:

```powershell
.\bump_patch.ps1 -BumpType major
.\bump_patch.ps1 -BumpType minor
.\bump_patch.ps1 -BumpType patch
```

任意のバージョンを直接指定する:

```powershell
.\bump_patch.ps1 -SpecificVersion 1.2.3
```

`-SpecificVersion` は `X.Y.Z` 形式のみ受け付けます。

## コントリビューション

コントリビューションは大歓迎です！機能の改善やバグ修正については、プルリクエストを送るか、イシューを作成してください。

## ライセンス

このプロジェクトはMITライセンスの下でライセンスしています。詳細については、LICENSEファイルをご覧ください。

## Sponsor

[![Sponsor](https://img.shields.io/badge/Sponsor-GitHub-181717?logo=github)](https://github.com/sponsors/fangface-hub)
