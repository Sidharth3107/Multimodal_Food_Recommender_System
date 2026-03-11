from __future__ import annotations

from dataclasses import dataclass, field


@dataclass(frozen=True, slots=True)
class DietRule:
    forbidden_terms: tuple[str, ...] = ()
    nutrient_maxima: dict[str, float] = field(default_factory=dict)
    description: str = ""


@dataclass(frozen=True, slots=True)
class VisualStyleProfile:
    likely_allergens: tuple[str, ...] = ()
    diet_conflicts: dict[str, str] = field(default_factory=dict)


OPENFOODFACTS_COLUMNS = [
    "code",
    "product_name",
    "main_category_en",
    "ingredients_text",
    "allergens_en",
    "traces_en",
    "nutrition-score-fr_100g",
    "nutrition_grade_fr",
    "energy_100g",
    "fat_100g",
    "saturated-fat_100g",
    "sugars_100g",
    "carbohydrates_100g",
    "proteins_100g",
    "salt_100g",
    "image_url",
]

ALLERGEN_SYNONYMS: dict[str, tuple[str, ...]] = {
    "milk": ("milk", "lactose", "whey", "casein", "butter", "cream", "cheese", "yogurt", "ghee"),
    "egg": ("egg", "eggs", "albumin"),
    "fish": ("fish", "anchovy", "salmon", "tuna", "cod", "tilapia"),
    "shellfish": ("shellfish", "crustacean", "shrimp", "crab", "lobster", "prawn", "clam", "oyster", "mussel"),
    "tree nuts": ("tree nut", "tree nuts", "almond", "walnut", "pecan", "cashew", "pistachio", "hazelnut", "macadamia"),
    "peanut": ("peanut", "peanuts", "groundnut"),
    "wheat": ("wheat", "gluten", "semolina", "farina", "durum", "spelt"),
    "soy": ("soy", "soybean", "soya", "soy lecithin", "tofu", "edamame"),
    "sesame": ("sesame", "tahini"),
    "mustard": ("mustard",),
    "celery": ("celery",),
    "sulfites": ("sulfite", "sulfites", "sulphite", "sulphites"),
}

DIET_RULES: dict[str, DietRule] = {
    "vegan": DietRule(
        forbidden_terms=(
            "milk",
            "cream",
            "cheese",
            "butter",
            "whey",
            "casein",
            "yogurt",
            "honey",
            "egg",
            "eggs",
            "gelatin",
            "beef",
            "pork",
            "chicken",
            "fish",
            "shellfish",
            "anchovy",
            "salmon",
            "tuna",
        ),
        description="No animal-derived ingredients.",
    ),
    "vegetarian": DietRule(
        forbidden_terms=("beef", "pork", "chicken", "fish", "shellfish", "gelatin", "anchovy", "tuna"),
        description="No meat or seafood.",
    ),
    "gluten-free": DietRule(
        forbidden_terms=("wheat", "barley", "rye", "semolina", "malt", "spelt", "triticale", "gluten"),
        description="Avoid gluten-containing grains.",
    ),
    "dairy-free": DietRule(
        forbidden_terms=("milk", "cream", "cheese", "butter", "whey", "casein", "yogurt", "ghee"),
        description="No dairy proteins or lactose-rich ingredients.",
    ),
    "keto": DietRule(
        forbidden_terms=("sugar", "glucose", "corn syrup", "starch", "maltodextrin", "honey"),
        nutrient_maxima={"carbohydrates_g": 15.0, "sugars_g": 5.0},
        description="Very low carbohydrate profile.",
    ),
    "low-sodium": DietRule(
        nutrient_maxima={"salt_g": 0.30},
        description="Keep sodium density low per 100 g.",
    ),
    "low-sugar": DietRule(
        nutrient_maxima={"sugars_g": 5.0},
        description="Keep added and free sugars low per 100 g.",
    ),
}

VISUAL_RISK_PRIORS: dict[str, float] = {
    "beet salad": 12.0,
    "seaweed salad": 18.0,
    "caprese salad": 26.0,
    "greek salad": 28.0,
    "miso soup": 22.0,
    "sushi": 35.0,
    "chicken curry": 55.0,
    "club sandwich": 62.0,
    "hamburger": 78.0,
    "hot dog": 82.0,
    "lasagna": 68.0,
    "macaroni and cheese": 86.0,
    "pizza": 74.0,
    "fried rice": 64.0,
    "ice cream": 84.0,
    "chocolate cake": 90.0,
    "donuts": 94.0,
    "bread pudding": 82.0,
    "pancakes": 70.0,
    "waffles": 72.0,
}

STYLE_ALTERNATIVE_HINTS: dict[str, tuple[str, ...]] = {
    "pizza": ("bruschetta", "greek salad", "caprese salad"),
    "burger": ("club sandwich", "greek salad", "beet salad"),
    "sandwich": ("greek salad", "beet salad", "caprese salad"),
    "pasta": ("bruschetta", "caprese salad", "miso soup"),
    "salad": ("seaweed salad", "beet salad", "caprese salad"),
}

VISUAL_STYLE_PROFILES: dict[str, VisualStyleProfile] = {
    "pizza": VisualStyleProfile(
        likely_allergens=("milk", "wheat"),
        diet_conflicts={
            "vegan": "Visual recovery suggests pizza, which commonly contains cheese and is not vegan.",
            "dairy-free": "Visual recovery suggests pizza, which commonly contains cheese and may not be dairy-free.",
            "gluten-free": "Visual recovery suggests pizza, which commonly uses a wheat crust and may not be gluten-free.",
        },
    ),
    "burger": VisualStyleProfile(
        likely_allergens=("wheat", "milk"),
        diet_conflicts={
            "vegetarian": "Visual recovery suggests a burger, which commonly includes a meat patty and is not vegetarian.",
            "vegan": "Visual recovery suggests a burger, which commonly includes meat or cheese and is not vegan.",
            "gluten-free": "Visual recovery suggests a burger, which commonly uses a wheat bun and may not be gluten-free.",
        },
    ),
    "sandwich": VisualStyleProfile(
        likely_allergens=("wheat", "milk"),
        diet_conflicts={
            "vegan": "Visual recovery suggests a sandwich, which commonly includes dairy or meat fillings and is not reliably vegan.",
            "gluten-free": "Visual recovery suggests a sandwich, which commonly uses bread and may not be gluten-free.",
        },
    ),
    "pasta": VisualStyleProfile(
        likely_allergens=("wheat", "milk"),
        diet_conflicts={
            "vegan": "Visual recovery suggests pasta, which commonly includes cheese or egg-based noodles and is not reliably vegan.",
            "gluten-free": "Visual recovery suggests pasta, which commonly uses wheat and may not be gluten-free.",
        },
    ),
    "salad": VisualStyleProfile(
        likely_allergens=(),
        diet_conflicts={},
    ),
}

FILENAME_STYLE_HINTS: dict[str, str] = {
    "pizza": "pizza",
    "pepperoni": "pizza",
    "margherita": "pizza",
    "slice": "pizza",
    "salad": "salad",
    "greens": "salad",
    "burger": "burger",
    "hamburger": "burger",
    "sandwich": "sandwich",
    "sub": "sandwich",
    "pasta": "pasta",
    "spaghetti": "pasta",
    "penne": "pasta",
}

DEFAULT_VISUAL_RISK = 45.0
NUTRITION_SCORE_MIN = -15.0
NUTRITION_SCORE_MAX = 40.0
LOW_CONFIDENCE_IMAGE_THRESHOLD = 0.45
