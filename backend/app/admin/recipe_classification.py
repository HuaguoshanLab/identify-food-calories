"""Conservative, staged annotations from explicit names and referenced dish descriptions.

These annotations drive planning eligibility but never claim complete ingredients.
Ambiguous traditional names stay unknown instead of borrowing an invented recipe.
"""

from app.admin.schemas import RecipeClassification

PURPOSE_LABELS = {
    "whole_meal": "整餐候选",
    "component": "组合组成项",
    "both": "两者皆可",
    "unknown": "待确认",
}
ROLE_LABELS = {
    "staple": "主食",
    "protein": "蛋白质菜",
    "vegetable": "蔬菜菜肴",
    "mixed_main": "混合主餐",
    "fruit": "水果",
    "dairy": "奶及替代品",
    "nuts_seeds": "坚果种子",
    "soup": "汤羹",
    "drink": "饮品",
    "side": "其他配菜",
    "unknown": "待确认",
}
TAG_LABELS = dict(
    zip(
        "rice wheat other_grain tuber pulses livestock poultry fish shellfish egg offal soy other_plant_protein leafy_veg stem_flower_veg fruit_veg root_veg mushroom algae fruit dairy plant_drink nuts seeds".split(),
        "米及制品 麦及制品 其他谷物 薯类 杂豆 畜肉 禽肉 鱼类 虾蟹贝类 蛋类 动物内脏 大豆及豆制品 其他植物蛋白制品 叶菜 花茎类 瓜茄类 根菜 菌菇 藻类 水果 奶及奶制品 植物替代饮品 坚果 种子".split(),
        strict=True,
    )
)

# A lexical signal supplies positive evidence only, not a complete ingredient list.
TAG_WORDS = {
    "rice": ("米饭", "炒饭", "糯米", "米粉", "米线", "米皮", "米糕", "米粿", "米粥"),
    "wheat": (
        "面条",
        "面饼",
        "面片",
        "面线",
        "面汤",
        "炒面",
        "拌面",
        "汤面",
        "凉面",
        "烩面",
        "牛肉面",
        "羊肉面",
        "馒头",
        "包子",
        "饺",
        "馄饨",
    ),
    "other_grain": ("玉米", "燕麦", "荞麦", "荞面", "青稞", "莜面", "小米"),
    "tuber": ("土豆", "洋芋", "地瓜", "红薯", "芋头", "芋儿", "芋泥"),
    "pulses": ("红豆", "绿豆", "豌豆"),
    "livestock": (
        "猪肉",
        "牛肉",
        "羊肉",
        "驴肉",
        "牦牛",
        "羊排",
        "羊羔",
        "全羊",
        "排骨",
        "肘子",
    ),
    "poultry": ("鸡", "鸭", "鹅", "鸽"),
    "fish": ("鱼", "鳝"),
    "shellfish": ("虾", "蟹", "蛤", "蚝", "扇贝", "海螺", "蛎", "蚵"),
    "egg": ("蛋",),
    "offal": ("猪肚", "大肠", "腰花", "脑花", "鸡杂", "羊肺", "炒肝", "爆肚"),
    "soy": ("豆腐", "豆浆", "腐皮", "豆花"),
    "other_plant_protein": ("烤麸",),
    "leafy_veg": ("青菜", "菠菜", "白菜", "酸菜", "梅菜"),
    "stem_flower_veg": ("笋", "菜花", "西兰花", "芹菜", "韭黄"),
    "fruit_veg": ("茄子", "南瓜", "苦瓜", "番茄", "四季豆"),
    "root_veg": ("萝卜", "莲藕"),
    "mushroom": ("蘑菇", "香菇", "野生菌", "鸡枞", "石耳"),
    "algae": ("海带", "紫菜"),
    "fruit": ("梨", "菠萝", "椰子", "柠檬", "葡萄", "荔枝", "柿子"),
    "dairy": ("牛奶", "酸奶", "奶酪", "奶皮", "奶渣", "奶豆腐"),
    "plant_drink": ("豆浆", "燕麦奶"),
    "nuts": ("花生", "核桃", "杏仁"),
    "seeds": ("芝麻", "瓜子"),
}

# Names that use metaphor or a regional dish name do not establish that ingredient.
MASKS = (
    "鱼香",
    "鸡枞",
    "鸡蛋",
    "鸡尾",
    "蟹壳",
    "菠萝包",
    "荔枝肉",
    "葡萄鱼",
    "奶豆腐",
    "米豆腐",
    "土笋冻",
)
EXACT_ROLES = {
    "白米饭": "staple",
    "壮族五色糯米饭": "staple",
    "冠头蒸馒头": "staple",
    "红烧鸡枞": "vegetable",
    "问政山笋": "vegetable",
    "剁椒蒸茄子": "vegetable",
    "地三鲜": "vegetable",
    "折耳根凉拌": "vegetable",
    "麻婆茄子": "vegetable",
    "奶豆腐": "dairy",
    "乳扇": "dairy",
    "乳饼": "dairy",
    "冻梨": "fruit",
    "菠萝包": "side",
    "蟹壳黄": "side",
    "冰糖葫芦": "side",
    "奶茶粥": "unknown",
    "奶黄包": "side",
    "双皮奶": "side",
    "姜撞奶": "side",
    "炸奶渣": "side",
    "炸奶皮": "side",
    "炸奶球": "side",
    "海蛎煎": "protein",
    "烤脑花": "protein",
    "蒜蓉粉丝蒸扇贝": "protein",
    "爆炒腰花": "protein",
    "莜面": "staple",
    "剁椒芋头": "staple",
    "铜锅洋芋": "staple",
    "芋泥": "staple",
    "四喜烤麸": "protein",
    "香菇烤麸": "protein",
    "土笋冻": "side",
    "龙抄手": "mixed_main",
    "拉条子": "mixed_main",
    "大救驾": "mixed_main",
    "腾冲大救驾": "mixed_main",
}


# These exact names make the culinary role explicit, without asserting hidden fillings.
EXACT_ROLES.update(dict.fromkeys((
    "煎饼", "炸玉米饼", "蒸玉米饼", "吉林玉米饼", "山东煎饼", "榆中煎饼",
    "玉门油饼", "上海葱油饼", "山东葱油饼", "藏式土豆饼", "芝麻烧饼",
    "平凉锅盔", "锅盔", "石子馍", "荞面饸饹", "定西土豆粉",
), "staple"))
EXACT_ROLES.update(dict.fromkeys((
    "桂花糯米藕", "重庆冰粉", "鲜花饼", "新疆炸南瓜饼", "椰子冻",
    "奶渣饼", "拔丝地瓜", "豌豆黄", "唐山地瓜丸", "油炸柿子饼",
    "鲜肉月饼", "酸奶米布丁", "北京地瓜球", "黄桂柿子饼", "火腿月饼",
    "奶皮卷", "酒酿圆子",
), "side"))
EXACT_ROLES.update(dict.fromkeys((
    "南昌拌粉", "南宁老友粉", "海南粉", "抱罗粉", "常德牛肉粉",
    "门钉肉饼", "蒙古牛肉饼", "宫廷牛肉饼", "藏式肉饼", "石家庄鸡蛋饼",
    "酸菜煎饼", "泡菜煎饼", "椰子饭", "藏式甜米饭", "菠萝饭", "担担饭",
    "吉林拌粉条", "酸辣粉", "螺蛳粉", "卷筒粉", "鸭血卷粉",
    "丁丁汤饭", "干炒牛河", "煎饼果子", "卤煮火烧", "炸云吞",
), "mixed_main"))
EXACT_ROLES.update(dict.fromkeys(("炸肝饼", "梅菜蒸肉饼", "虾饼", "客家酿腐皮卷"), "protein"))
EXACT_ROLES["奶汤蒲菜"] = "soup"
EXACT_ROLES["酸菜炖粉条"] = "side"


# Public descriptions resolve a dish family, never this catalog entry's full recipe.
REFERENCE_ROLES = {
    "糌粑": ("staple", ("other_grain",), "https://www.shannan.gov.cn/zjsn/snly/tsms/201903/t20190328_24421.html"),
    "大煮干丝": ("protein", ("soy",), "https://www.nhc.gov.cn/xcs/c100122/202411/f63a9692d1294dd19c595dce73404417.shtml"),
    "叉烧": ("protein", (), "https://www.samr.gov.cn/spcjs/yjjl/art/2024/art_68c480e7ac4647ed9612197d7cf5e38f.html"),
    "片儿川": ("mixed_main", (), "https://zh.wikipedia.org/wiki/片儿川"),
}
EXACT_ROLES.update({name: value[0] for name, value in REFERENCE_ROLES.items()})


def classify_recipe(name: str) -> RecipeClassification:
    evidence = []
    if name in EXACT_ROLES:
        role = EXACT_ROLES[name]
        evidence.append("菜名明确归类")
    elif any(word in name for word in ("奶茶", "酥油茶", "豆汁", "米酒")):
        role = "drink"
    elif any(
        word in name
        for word in (
            "炒饭",
            "盖饭",
            "煲仔饭",
            "抓饭",
            "菜饭",
            "萝卜饭",
            "肉夹馍",
            "羊肉夹馍",
            "馕包肉",
            "羊肉馕",
            "肉馕",
            "糯米鸡",
            "饺",
            "馄饨",
            "包子",
            "小笼包",
            "生煎包",
            "灌汤包",
            "烧卖",
            "肠粉",
            "米线",
            "河粉",
            "米粉",
            "炒面",
            "拌面",
            "汤面",
            "凉面",
            "烩面",
            "面汤",
            "面片汤",
            "面线",
            "臊子面",
            "牛肉面",
            "羊肉面",
            "酱面",
            "沙茶面",
            "担担面",
            "阳春面",
            "小面",
            "泡馍",
            "云吞面",
            "牛腩面",
            "粢饭团",
            "粽子",
            "肉粽",
            "皮蛋瘦肉粥",
        )
    ):
        role = "mixed_main"
    elif name.endswith(("面", "包", "饼", "粉", "饵丝", "锅贴", "锅盔", "烧饼")):
        role = (
            "mixed_main" if name.endswith(("面", "包", "锅贴", "饵丝")) else "unknown"
        )
    elif name.endswith(("汤", "羹")):
        role = "soup"
    elif any(
        word in name
        for word in ("酸奶", "牛奶", "奶酪", "奶皮", "奶渣", "奶豆腐", "豆浆")
    ) and not any(word in name for word in ("饼", "卷", "粥", "布丁", "炸")):
        role = "dairy"
    elif (
        any(
            word in name
            for word in (
                "馒头",
                "白米饭",
                "糯米饭",
                "竹筒饭",
                "小米粥",
                "燕麦粥",
                "青稞粥",
            )
        )
        or name == "馕"
    ):
        role = "staple"
    elif any(
        word in name
        for word in (
            "糕",
            "麻花",
            "糖",
            "酥",
            "月饼",
            "花饼",
            "汤圆",
            "糍粑",
            "粑粑",
            "冰粉",
            "冰淇淋",
        )
    ):
        role = "side"
    elif any(
        word in name
        for word in ("火锅", "杂烩", "一品锅", "冒菜", "香锅", "水席", "串串", "炖菜")
    ):
        role = "unknown"
    else:
        masked = name.replace("鱼香", "").replace("鸡枞", "").replace("米豆腐", "")
        if any(
            word in masked
            for word in (
                "肉",
                "鱼",
                "鸡",
                "鸭",
                "鹅",
                "虾",
                "蟹",
                "蛋",
                "豆腐",
                "豆花",
                "羊排",
                "排骨",
                "肘子",
                "肠",
                "肝",
                "肚",
                "鸽",
                "鱿鱼",
                "蛤",
                "蚝",
                "螺",
                "蛙",
                "兔",
                "鳝",
                "河鳗",
                "河豚",
                "全羊",
                "火腿",
                "凤爪",
                "腰花",
                "扇贝",
                "海参",
            )
        ):
            role = "protein"
        elif any(word in masked for word in ("茄子", "四季豆", "蘑菇", "青菜")):
            role = "vegetable"
        else:
            role = "unknown"
    # A mixed name is a candidate for a meal, not proof of balanced nutrition.
    purpose = (
        "whole_meal"
        if role == "mixed_main"
        else "unknown"
        if role == "unknown"
        else "component"
    )
    name_for_tags = name
    for word in MASKS:
        # Mask only the metaphor; retain the real ingredient suffix where present.
        replacement = {
            "鸡蛋": "蛋",
            "鸡枞": "菌",
            "葡萄鱼": "鱼",
            "荔枝肉": "肉",
            "奶豆腐": "奶酪",
        }.get(word, "")
        name_for_tags = name_for_tags.replace(word, replacement)
    tags = [
        tag
        for tag, words in TAG_WORDS.items()
        if any(word in name_for_tags for word in words)
    ]
    if any(word in name for word in ("鱿鱼", "甲鱼", "鲍鱼")) and "fish" in tags:
        tags.remove("fish")
    if any(word in name for word in ("鱿鱼", "鲍鱼")) and "shellfish" not in tags:
        tags.append("shellfish")
    if "鸡枞" in name and "mushroom" not in tags:
        tags.append("mushroom")
    if name in REFERENCE_ROLES:
        _, known_tags, source = REFERENCE_ROLES[name]
        tags = list(dict.fromkeys([*tags, *known_tags]))
        evidence.append(f"公开菜品类别参考：{source}；不代表本条完整配料")
    evidence.append("依据菜名可识别线索；未推断未明示配料")
    if role == "unknown":
        evidence.append("地方菜名或混合构成不明确，用途和角色待确认")
    if not tags:
        evidence.append("暂无足够食材标签证据")
    return RecipeClassification(
        basis="name_only",
        purpose=purpose,
        role=role,
        ingredient_tags=tuple(tags),
        evidence="；".join(evidence),
    )
