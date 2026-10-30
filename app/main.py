"""
App Package Entrypoint for HocNhanhTN.
Chỉ gọi App Factory `create_app()` và cấu hình Uvicorn server runner.
"""

from app.config.settings import settings
from app.core.app_factory import create_app

app = create_app()

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        "app.main:app",
        host=settings.HOST,
        port=settings.PORT,
        reload=settings.RELOAD,
    )
