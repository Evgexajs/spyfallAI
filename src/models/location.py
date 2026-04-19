"""Location and Role models for SpyfallAI."""

from pydantic import BaseModel, Field, field_validator


class Role(BaseModel):
    """Role within a location."""

    id: str = Field(min_length=1, description="Unique slug: surgeon, patient")
    display_name: str = Field(min_length=1, description="Display name for the role")
    description: str = Field(min_length=1, description="Short description of responsibilities")


class Location(BaseModel):
    """Location in the game."""

    id: str = Field(min_length=1, description="Unique slug: hospital, airplane")
    display_name: str = Field(min_length=1, description="Display name for the location")
    description: str = Field(min_length=1, description="Short atmosphere description (1-2 sentences)")
    roles: list[Role] = Field(min_length=3, max_length=5, description="3-5 roles for this location")

    @field_validator("roles")
    @classmethod
    def validate_unique_role_ids(cls, v: list[Role]) -> list[Role]:
        role_ids = [role.id for role in v]
        if len(role_ids) != len(set(role_ids)):
            raise ValueError("Role IDs must be unique within a location")
        return v
