# MacBook（開発機） で Docker Desktop なしに Docker を使う方法

Docker Desktop は個人利用なら無料だが、起動が重くメモリ消費も大きい。  
軽量な代替として **Colima + Docker CLI** を使う方法をまとめる。

---

## 開発機のスペック

### MacBook Pro
- **プロセッサ:**　2.6 GHz 6コアIntel Core i7
- **グラフィックス:**　Intel UHD Graphics 630 1536 MB
- **メモリ:**　16 GB 2667 MHz DDR4

---

## 構成

```
Homebrew
├── docker          # Docker CLI（コマンドだけ。デーモンは含まない）
├── docker-compose  # Compose CLI
└── colima          # macOS 上で Linux VM を起動し Docker デーモンを動かす
```

Colima は内部で Lima（macOS 向け Linux VM）を使い、その中で Docker デーモンを動かす。  
`docker` コマンドはソケット経由で Colima のデーモンに繋ぐ。

---

## セットアップ手順

### 1. Homebrew でインストール

```bash
brew install docker docker-compose colima
```

### 2. Colima を起動

```bash
colima start
```

初回は VM イメージのダウンロードがあるため数分かかる。  
以降の起動は 10〜20 秒程度。

リソースを明示したい場合（省略時はデフォルト値が使われる）：

```bash
colima start --cpu 2 --memory 4 --disk 60
```

### 3. Docker が使えるか確認

```bash
docker info
docker version
```

`Server:` セクションに情報が出れば OK。

---

## プリクラアプリで試す

```bash
cd /path/to/prikura

docker compose up --build
# → http://localhost でアクセス（想定）
```

> ⚠️ Docker 構成ファイルは用意しているが動作未検証。  
> nginx Dockerfile が `assets/fonts/`・`assets/sounds/`・`assets/stamps/` を  
> コンテナにコピーしていないため、フォント・BGM・スタンプが動かない可能性がある。

---

## Colima の基本操作

| コマンド | 内容 |
|---|---|
| `colima start` | VM 起動（Docker デーモンも起動） |
| `colima stop` | VM 停止 |
| `colima status` | 起動状態を確認 |
| `colima delete` | VM を完全削除（ディスク領域を解放） |
| `colima start --edit` | CPU / メモリ / ディスクをエディタで変更 |

---

## ログイン時に自動起動したい場合

```bash
# launchd サービスとして登録
colima start --foreground=false
brew services start colima
```

---

## アンインストール

```bash
colima delete        # VM 削除
brew uninstall colima docker docker-compose
```

---

## トラブルシューティング

### `Cannot connect to the Docker daemon` と出る

Colima が起動していない。`colima start` を実行する。

### `docker compose` が `docker-compose` と認識されない

```bash
mkdir -p ~/.docker/cli-plugins
ln -sfn $(brew --prefix)/opt/docker-compose/bin/docker-compose \
    ~/.docker/cli-plugins/docker-compose
```

### Apple Silicon (M1/M2/M3) でイメージが動かない

`linux/amd64` イメージを ARM で動かす場合はエミュレーションが必要：

```bash
colima start --arch aarch64 --vm-type vz --vz-rosetta
```

または `--arch x86_64` で x86_64 VM として起動（遅いが互換性が高い）：

```bash
colima start --arch x86_64
```
