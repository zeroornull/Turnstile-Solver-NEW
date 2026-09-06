# Docker 部署：镜像内置浏览器

镜像包含 Python、项目依赖、Chromium 及其 Linux 系统依赖。容器启动时直接使用镜像中的浏览器，不运行 `pip install` 或浏览器下载命令，宿主机也不需要安装 Python、Chrome。

首次构建需要联网拉取基础镜像、Python 包和浏览器。构建完成后，可以用 `docker save` 导出整个镜像，在另一台机器上用 `docker load` 导入；启动时不再下载浏览器。访问目标网站仍然需要网络，这不是离线解题镜像。

## 使用 GitHub 上的预构建镜像

镜像地址：`ghcr.io/zeroornull/turnstile-solver-new:latest`，支持 `linux/amd64` 和 `linux/arm64`。由 GitHub Actions 构建并发布到 [本仓库](https://github.com/zeroornull/Turnstile-Solver-NEW) 的 GitHub Packages；`docker pull` 会按宿主机架构选择对应镜像。压缩包不会提交到 Git。

如果镜像包是私有的，先执行 `docker login ghcr.io`，使用有权访问该包的 GitHub 账号登录；密码处输入具有 `read:packages` 权限的 classic PAT，而不是 GitHub 登录密码。不要把 PAT 写进脚本或提交到仓库。

```bash
docker pull ghcr.io/zeroornull/turnstile-solver-new:latest

docker run -d \
  --name turnstile-solver \
  --init \
  --restart unless-stopped \
  --shm-size=1g \
  -p 127.0.0.1:5072:5072 \
  ghcr.io/zeroornull/turnstile-solver-new:latest
```

拉取镜像时会一次性下载包括浏览器在内的镜像层；容器启动时不会再单独下载浏览器。`latest` 指向默认分支最近一次成功发布，`sha-<提交短哈希>` 标签用于定位对应代码版本。推送到 `master`、推送 `v*` 标签，或手动运行 **Publish container image** 工作流都会构建并推送双架构镜像。

## 构建与启动

在项目根目录执行：

```bash
docker build -t turnstile-solver:local .

docker run -d \
  --name turnstile-solver \
  --init \
  --restart unless-stopped \
  --shm-size=1g \
  -p 127.0.0.1:5072:5072 \
  turnstile-solver:local

docker logs -f turnstile-solver
```

打开 <http://127.0.0.1:5072>。默认无头运行、最多同时处理 4 个任务，容器内监听 `0.0.0.0:5072`。

`--init` 用来回收浏览器子进程，`--shm-size=1g` 为 Chromium 提供更大的共享内存。镜像使用非 root 用户运行。API 没有鉴权，示例仅绑定宿主机的回环地址；不要直接暴露到公网。需要远程访问时，应先配置带鉴权的反向代理或使用受控的私有网络。

Docker 默认使用 `--browser_type chromium`，与本地 `python api.py` 默认的 `chrome` 不同。只预装 Chromium，不包含 Chrome、Edge 或 Camoufox；直接切换到这些浏览器会因未安装而失败。容器未配置显示会话，不要直接传 `--no-headless`。

## 修改启动参数

镜像名后面可以追加 `api.py` 支持的参数，例如调整并发并开启日志：

```bash
docker run --rm --init --shm-size=1g \
  -p 127.0.0.1:5072:5072 \
  turnstile-solver:local --thread 2 --debug
```

如需更换宿主机端口，把映射改成 `-p 127.0.0.1:5080:5072` 即可，不必修改容器内端口。上面的命令与默认示例使用相同的宿主机端口，不能同时运行。

## 使用代理文件

`proxies.txt` 不会进入构建上下文，避免将代理账号和密码打包进镜像。镜像内提供空的 `/app/proxies.txt`。需要随机代理时，将本地文件只读挂载进去，并开启 `--proxy`：

```bash
docker run --rm --init --shm-size=1g \
  -p 127.0.0.1:5072:5072 \
  --mount type=bind,src="$(pwd)/proxies.txt",dst=/app/proxies.txt,readonly \
  turnstile-solver:local --proxy
```

确保挂载文件可被容器内 UID `10001` 的用户读取。`/cf_clearance` 接口也支持通过请求参数单独指定代理。

## 导出镜像，部署时无需下载浏览器

构建机器上执行：

```bash
docker save -o turnstile-solver.tar turnstile-solver:local
```

将 `turnstile-solver.tar` 复制到目标机器，然后执行：

```bash
docker load -i turnstile-solver.tar

docker run -d \
  --name turnstile-solver \
  --pull=never \
  --init \
  --restart unless-stopped \
  --shm-size=1g \
  -p 127.0.0.1:5072:5072 \
  turnstile-solver:local
```

目标机器需要 Docker，并使用与镜像匹配的 CPU 架构。跨架构部署时，先在构建机上为目标平台构建，例如 `docker buildx build --platform linux/amd64 --load -t turnstile-solver:local .`，再导出。

不要用宿主机目录覆盖 `/ms-playwright`，也不要在现有容器中单独升级 Patchright，否则可能覆盖浏览器文件或造成驱动版本不匹配。需要升级时重新构建镜像。

Dockerfile 默认固定 Patchright `1.62.3`，安装与它匹配的完整 Chromium，不额外安装 headless shell。升级时可以通过 `--build-arg PATCHRIGHT_VERSION=<版本号>` 覆盖，并重新运行下面的断网测试。其余 Python 依赖沿用项目的 `requirements.txt`。

## 断网验证

下面的测试容器不连接外部网络，也不发布端口。测试会检查 API 首页、参数校验，以及通过项目自己的 `launch_browser()` 启动内置 Chromium、渲染本地 HTML。它不访问 Cloudflare，也不验证真实挑战的通过率。

```bash
docker run -d --name turnstile-solver-smoke \
  --network none --init --shm-size=1g \
  turnstile-solver:local

docker exec -i turnstile-solver-smoke python - < tests/docker_smoke.py

docker stop turnstile-solver-smoke
docker rm turnstile-solver-smoke
```

测试通过后，说明 API 与浏览器在无外网环境下可以启动，不依赖运行时下载。
