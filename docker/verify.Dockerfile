# 一次性校验镜像：运行 pytest（单元 + 穷举核对 + API 契约 + 对活服务的 HTTP 冒烟）
FROM python:3.13-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    API_BASE_URL=http://api:8000

WORKDIR /srv

COPY api/requirements.txt api/requirements-dev.txt ./
RUN pip install --no-cache-dir -r requirements-dev.txt

COPY api/app ./app
COPY api/tests ./tests
COPY api/pyproject.toml ./

# 跑完即退出；退出码即测试结果
CMD ["pytest", "-q"]
