"""
每日挑战任务库 — 预置摄影挑战任务。
"""
import hashlib
from datetime import date

CHALLENGES = [
    # === 构图方向 ===
    {
        "id": "rule-of-thirds",
        "title": "三分法构图",
        "description": "拍摄一张严格遵循三分法构图的照片。将主体放在画面的四个交叉点之一上，或者让地平线/水平线与三分线对齐。",
        "criteria": "主体明确放置在三分线交叉点；画面平衡不倾斜；背景不过度干扰主体",
        "difficulty": 1,
    },
    {
        "id": "leading-lines",
        "title": "引导线构图",
        "description": "利用道路、栏杆、河流、建筑边缘等线条，引导观众视线到画面主体或远方。",
        "criteria": "画面中有明显的引导线；引导线指向主体或趣味中心；线条不被切断或突兀中断",
        "difficulty": 1,
    },
    {
        "id": "negative-space",
        "title": "留白之美",
        "description": "拍摄一张运用大面积留白（负空间）的照片，让主体在简约的背景中突出。适合天空、墙壁、水面等简洁背景。",
        "criteria": "画面有明显留白区域；主体突出不杂乱；留白比例恰当（不少于1/3画面）",
        "difficulty": 2,
    },
    {
        "id": "frame-within-frame",
        "title": "框中框构图",
        "description": '利用门框、窗户、拱门、树枝等自然框架将主体\u201c框\u201d起来，增加画面层次感和纵深感。',
        "criteria": "画面中存在明显的框架元素；主体在框架内；框架增强了画面层次",
        "difficulty": 2,
    },

    # === 光线方向 ===
    {
        "id": "golden-hour",
        "title": "黄金时刻",
        "description": "在日出后或日落前一小时内拍摄，利用温暖柔和的低角度光线营造氛围。题材不限。",
        "criteria": "照片有明显暖色调光线特征；影子长而柔和；光线角度低（非正午顶光）",
        "difficulty": 2,
    },
    {
        "id": "backlight",
        "title": "逆光剪影",
        "description": "对着光源拍摄，让主体呈现剪影效果。注意主体的轮廓要清晰可辨。",
        "criteria": "光源在主体后方；主体呈剪影或半剪影效果；主体轮廓清晰可辨识",
        "difficulty": 2,
    },
    {
        "id": "shadow-play",
        "title": "光影游戏",
        "description": "拍摄有趣的影子——可以是人的影子、树影、建筑投影等。影子本身应成为画面的视觉焦点。",
        "criteria": "影子是画面的主要视觉元素；光线和影子的对比有视觉冲击力；构图包含影子与产生影子的物体之间的关系",
        "difficulty": 1,
    },

    # === 色彩方向 ===
    {
        "id": "monochrome-color",
        "title": "单色世界",
        "description": "拍摄一张以单一色调为主的照片。画面中80%以上的颜色属于同一色系（如全蓝、全绿、全红等），但仍保留丰富的明暗层次。",
        "criteria": "主色调占比超过80%；同一色系内有明暗变化；画面不单调乏味",
        "difficulty": 1,
    },
    {
        "id": "complementary",
        "title": "补色碰撞",
        "description": "拍摄一张运用互补色（如蓝橙、红绿、黄紫）的照片，利用色彩对比创造视觉张力。",
        "criteria": "画面中存在明显的互补色对比；色彩饱和度和明度搭配协调；色彩对比服务于构图",
        "difficulty": 2,
    },

    # === 人像方向 ===
    {
        "id": "candid-portrait",
        "title": "抓拍瞬间",
        "description": "拍摄一张不摆拍的人像照片。捕捉人物自然的表情、动作或互动瞬间。可以是街头抓拍、家庭生活、朋友聚会等。",
        "criteria": "人物表情/动作自然不刻意；捕捉到了有故事感的瞬间；对焦清晰（尤其是眼睛）",
        "difficulty": 3,
    },
    {
        "id": "hands-story",
        "title": "手的故事",
        "description": "特写拍摄一双手——可以是正在工作的手、弹琴的手、做手工的手、老人的手等。通过手传递情绪或故事。",
        "criteria": "手是画面主体；光线上能体现手部纹理/细节；通过手能感知到情绪或故事",
        "difficulty": 2,
    },

    # === 静物/微距方向 ===
    {
        "id": "texture",
        "title": "质感特写",
        "description": '近距离拍摄物体的表面纹理——木头纹路、布料纤维、食物切面、树叶脉络、金属拉丝等。让观者几乎能\u201c摸到\u201d画面。',
        "criteria": "主体纹理清晰可见；对焦精准；光线方向利于展现纹理（侧光为佳）",
        "difficulty": 2,
    },
    {
        "id": "reflection",
        "title": "镜像世界",
        "description": "利用水面、玻璃、镜子、金属表面等反光物体拍摄倒影或反射。反射内容应与现实形成有趣的对比或延伸。",
        "criteria": "画面中有清晰的反射/倒影元素；反射内容与实景形成构图关系；曝光准确（反射面不过曝）",
        "difficulty": 2,
    },

    # === 街拍/城市方向 ===
    {
        "id": "geometry-urban",
        "title": "城市几何",
        "description": "拍摄建筑或城市空间中重复的几何图形——楼梯的螺旋、窗户的阵列、桥梁的结构线条等。追求秩序感和节奏感。",
        "criteria": "画面以几何图形/重复图案为主体；构图工整有秩序感；透视控制得当",
        "difficulty": 1,
    },
    {
        "id": "contrast-old-new",
        "title": "新旧对比",
        "description": "在同一画面中捕捉新与旧的对比——古建筑与摩天楼、老手艺与新技术、传统与现代的并置。",
        "criteria": "画面中同时存在新旧元素；对比关系清晰明确；构图有意识地并置两者",
        "difficulty": 3,
    },
]


def get_daily_challenge() -> dict:
    """根据当天日期返回每日挑战（确定性轮换）。"""
    today = date.today().isoformat()
    idx = int(hashlib.md5(today.encode()).hexdigest(), 16) % len(CHALLENGES)
    return CHALLENGES[idx]


def get_challenge_by_id(challenge_id: str) -> dict | None:
    """按 ID 获取挑战详情。"""
    for c in CHALLENGES:
        if c["id"] == challenge_id:
            return c
    return None
