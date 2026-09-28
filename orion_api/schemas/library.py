from pydantic import BaseModel, Field


class LibraryUpdate(BaseModel):
    paper_id: str = Field(min_length=1, max_length=500)
    favorite: bool = True
