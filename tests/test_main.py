import expand_latex_macros as elm

# flap command


def test_main():
    with open("latex-src/main.tex", 'r') as src:
        new_tex = src.read()
    # with open("test-output/merged.tex", 'w') as out:
    #     out.write(new_tex)
    with open("latex-target/main-expanded.tex", 'r') as target:
        target_tex = target.read()
    assert new_tex == target_tex
