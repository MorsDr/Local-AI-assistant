import json
from prompt_generator import generate_prompts

TEST_CASES = [
    "Партрэт пажылога чараўніка з доўгай сівой барадой.",
    "Поўнафігурны 3D-персанаж: маленькая чырвоная панда-вынаходнік.",
    "Фотарэалістычны горны пейзаж на досвітку.",
    "Мінімалістычная белая керамічная ваза на светлым фоне.",
    "Руды кот сядзіць на сінім крэсле ў пустым пакоі. Толькі кот і крэсла, без іншых прадметаў.",
]

for index, request in enumerate(TEST_CASES, start=1):
    print(f"\n{'=' * 60}")
    print(f"ТЭСТ {index}: {request}")

    try:
        result = generate_prompts(request)

        assert set(result) == {
            "positive_prompt",
            "negative_prompt",
        }
        assert all(
            isinstance(result[key], str) and result[key].strip()
            for key in result
        )

        print(json.dumps(result, ensure_ascii=False, indent=2))
        print("ВЫНІК: PASS — структура адказу правільная")

    except Exception as error:
        print(f"ВЫНІК: FAIL — {error}")
