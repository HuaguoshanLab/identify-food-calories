"""Versioned recipe classification shared by administration and planning."""
from typing import Literal
from pydantic import BaseModel, ConfigDict, Field, field_validator

RecipePurpose = Literal["whole_meal", "component", "both", "unknown"]
RecipeRole = Literal["staple", "protein", "vegetable", "mixed_main", "fruit", "dairy", "nuts_seeds", "soup", "drink", "side", "unknown"]
IngredientTag = Literal["rice", "wheat", "other_grain", "tuber", "pulses", "livestock", "poultry", "fish", "shellfish", "egg", "offal", "soy", "other_plant_protein", "leafy_veg", "stem_flower_veg", "fruit_veg", "root_veg", "mushroom", "algae", "fruit", "dairy", "plant_drink", "nuts", "seeds"]


class RecipeClassification(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)
    version: Literal["recipe-classification.v1"] = "recipe-classification.v1"
    purpose: RecipePurpose
    role: RecipeRole
    ingredient_tags: tuple[IngredientTag, ...] = Field(max_length=24)
    evidence: str = Field(min_length=1, max_length=500)
    # Name-based annotations are not a complete ingredient or allergen list.
    basis: Literal["name_only", "name_and_legacy_role", "admin_review"] = "name_only"

    @property
    def supports_user_exclusions(self) -> bool:
        """Only reviewed ingredient evidence may enforce an exclusion."""
        return self.basis == "admin_review"

    @field_validator("ingredient_tags")
    @classmethod
    def unique_tags(cls, value):
        if len(set(value)) != len(value):
            raise ValueError("duplicate tags")
        return value



# Broad categories only: a livestock tag cannot establish pork or beef specifically.
_EXCLUSION_LABELS = {
    "rice": ("米",), "wheat": ("小麦", "麦制品"), "other_grain": ("杂粮",),
    "tuber": ("薯类",), "pulses": ("杂豆",), "livestock": ("畜肉", "肉"),
    "poultry": ("禽肉", "肉"), "fish": ("鱼",), "shellfish": ("海鲜", "虾蟹贝类"),
    "egg": ("蛋",), "offal": ("内脏",), "soy": ("大豆", "豆制品"),
    "other_plant_protein": ("植物蛋白制品",), "leafy_veg": ("叶菜",),
    "stem_flower_veg": ("花茎菜",), "fruit_veg": ("瓜茄",), "root_veg": ("根菜",),
    "mushroom": ("菌菇",), "algae": ("藻类",), "fruit": ("水果",),
    "dairy": ("奶", "乳制品"), "plant_drink": ("植物饮品",),
    "nuts": ("坚果",), "seeds": ("种子",),
}


def ingredient_exclusion_labels(tags: tuple[IngredientTag, ...]) -> tuple[str, ...]:
    """Known categories add exclusion evidence; absence never means allergen-free."""
    return tuple(label for tag in tags for label in _EXCLUSION_LABELS[tag])
