# 将完整工程上 GitHub（优先私有仓库）

GitHub 尚未连接时，不要将本步骤误写为已完成。当前仓库的质量检查工作流放在 `.github/workflows/quality.yml`。

**已有仓库：** 首选连接用户 GitHub 后，先查看 `README`、分支和已有文件；创建 `integration/feishu-h5` 分支提交，使用 PR 合并；不允许强制推送覆盖旧仓库。

**新仓库：** 用户账户下新建 `medrep-coach` PRIVATE（默认不勾选生成 README / .gitignore，避免额外历史），在可信开发终端中解压源码后运行：

```bash
cd medrep-coach
python scripts/prepublish_check.py
git init -b main
git add .
git status --short
git commit -m 'Prepare MedRep Coach Feishu H5 and dual practice flows'
git remote add origin https://github.com/OWNER/medrep-coach.git
git push -u origin main
```

`OWNER` 必须由用户确认，推送需用户本人授权 GitHub。上面的命令是操作说明，**本交付包没有代替用户执行远程 push**。如仓库已有内容，不使用这个初始化方式。

企业二次使用仍需要自己的飞书自建应用和独立服务环境，不能直接用 GitHub 仓库 URL 当飞书网页主页。
