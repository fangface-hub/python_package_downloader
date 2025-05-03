# pythonパッケージダウンローダー

このプロジェクトは、指定されたプラットフォームやPythonバージョンに対応したパッケージをダウンロードできるPythonパッケージダウンローダーです。さまざまな環境での依存関係管理を簡単にすることを目的としています。

## プロジェクト構成

```text
python_package_downloader
├── python_package_downloader.py  # パッケージダウンローダーのメインスクリプト
├── requirements.txt              # 依存関係のあるPythonパッケージのリスト
├── .gitignore                    # Gitで無視するファイルやディレクトリ
└── README.md                     # プロジェクトのドキュメント
```

## インストール

### 仮想環境のセットアップ

1. 仮想環境を作成する:

```powershell
python -m venv .venv
```

1. 仮想環境を有効化する:

```powershell
.\.venv\Scripts\Activate.ps1
```

1. 必要な依存関係をインストールする:

```powershell
pip install -r requirements.txt
```

**注:** pipを使用してダウンロードする場合は、依存関係のインストールは不要です。

## 使用方法

1. リポジトリをダウンロードして、python_package_downloader.py を実行する

1. ダウンロード情報を入力する

    画面項目は以下のとおり。

    | 画面項目 | 説明 |
    | ---- | ---- |
    | ダウンロード方法 | 必須項目<br>PyPISimpleとrequestsが未インストールの場合は強制的にpipを使う。<br>pipを使う： ダウンロード環境の pip を使って pip download する <br> pipを使わない： PyPISimpleとrequestsを使用してパッケージをダウンロードする |
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

### 通常のビルド

1. PyInstaller をインストールする（requirements.txtに含まれています）

1. 以下のコマンドでビルドする

```powershell
pyinstaller PythonPackageDownloader.spec
```

実行ファイルは `dist/PythonPackageDownloader` フォルダに生成します。

### ビルドと自己署名（推奨）

WindowsDefenderの誤検知を避けるため、ビルド後に自己署名することを推奨します。

1. **管理者権限**でPowerShellを起動する

1. `build_and_sign.ps1` を編集して、以下の設定を変更する
   - `$certName`: 証明書の名前
   - `$orgName`: 組織名
   - `$pfxPassword`: 証明書のパスワード

1. PowerShellスクリプトを実行する

```powershell
.\build_and_sign.ps1
```

このスクリプトは以下の処理を自動的に行います：

- PyInstallerでビルド
- PowerShellのNew-SelfSignedCertificateで自己証明書を作成（初回のみ）
- 実行ファイルへの署名
- 署名の検証

証明書は `certificates` フォルダに保存し、2回目以降は再利用します。

## コントリビューション

コントリビューションは大歓迎です！機能の改善やバグ修正については、プルリクエストを送るか、イシューを作成してください。

## ライセンス

このプロジェクトはMITライセンスの下でライセンスしています。詳細については、LICENSEファイルをご覧ください。
