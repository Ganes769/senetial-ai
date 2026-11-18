from fastapi import APIRouter,HTTPException
from app.database import engine
from sqlalchemy import  text
from app.database import engine
from dotenv import load_dotenv
router=APIRouter(prefix="/api/v1/themes",tags=["Themes"])
@router.get("/")
def get_themes():
    try:
        with engine.connect() as connection:
            result=connection.execute(    text("""
                    SELECT id, name, description
                    FROM themes
                    WHERE is_active = TRUE
                    ORDER BY id
                """))
            themes = [
                dict(row._mapping)
                for row in result
            ]

        return {
            "count": len(themes),
            "themes": themes
        }

    except Exception as error:
        raise HTTPException(
            status_code=500,
            detail=str(error)
        )