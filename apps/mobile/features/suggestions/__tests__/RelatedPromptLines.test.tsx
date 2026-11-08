import { act, cleanup, fireEvent, render } from "@testing-library/react-native";
import { Dimensions } from "react-native";

import { nestedAccessibleElements } from "@/components/__tests__/a11yTree";
import { readLine, type Element } from "@/components/__tests__/support/mathInk";
import { RelatedPromptLines } from "@/features/suggestions/components/RelatedPromptLines";
import { spokenPrompt } from "@/features/suggestions/model/promptMath";

const PHYSICS =
  "Why is the force the product of mass and acceleration for this object?";
const MATH =
  "Why does the equation X^2 = 9 have two solutions, +3 and -3, instead of just one?";

describe("RelatedPromptLines", () => {
  afterEach(() => {
    cleanup();
  });

  it("sends the full question when the line is pressed", async () => {
    const onSelect = jest.fn();
    const { getByLabelText, getAllByRole, getAllByTestId, queryByTestId, queryByText } =
      await render(<RelatedPromptLines prompts={[MATH, PHYSICS]} onSelect={onSelect} />);

    expect(queryByText("X^2 = 9")).toBeNull();
    expect(getAllByRole("button")).toHaveLength(2);
    // A dotted underline under each question's words; no rules between rows.
    expect(getAllByTestId("related-prompt-underline")).toHaveLength(2);
    expect(queryByTestId("related-prompt-divider")).toBeNull();

    await act(async () => {
      fireEvent.press(getByLabelText(spokenPrompt(MATH)));
    });
    expect(onSelect).toHaveBeenCalledWith(MATH);
    await act(async () => {
      fireEvent.press(getByLabelText(PHYSICS));
    });
    expect(onSelect).toHaveBeenLastCalledWith(PHYSICS);
  });

  it("does not offer a fragment or a glued equation", async () => {
    const onSelect = jest.fn();
    const { queryByLabelText, getByLabelText } = await render(
      <RelatedPromptLines
        prompts={["How", "Education level", String.raw`Why does $^5\sqrt{x}=0^5$ equal zero?`, MATH]}
        onSelect={onSelect}
      />,
    );

    expect(queryByLabelText("How")).toBeNull();
    expect(queryByLabelText("Education level")).toBeNull();
    fireEvent.press(getByLabelText(spokenPrompt(MATH)));
    expect(onSelect).toHaveBeenCalledWith(MATH);
  });
});

describe("RelatedPromptLines for a screen reader", () => {
  afterEach(() => {
    cleanup();
  });

  it("labels a maths follow-up with its words, never its LaTeX", async () => {
    const prompt = String.raw`What if $v_f = 36\text{ km/h}$?`;
    const onSelect = jest.fn();
    const { getAllByRole, getByLabelText } = await render(
      <RelatedPromptLines prompts={[prompt]} onSelect={onSelect} />,
    );
    const [button] = getAllByRole("button");
    expect(button!.props.accessibilityLabel).toBe("What if v subscript f = 36 km/h?");
    fireEvent.press(getByLabelText("What if v subscript f = 36 km/h?"));
    expect(onSelect).toHaveBeenCalledWith(prompt);
  });

  it("keeps the line inside the button from being a second TalkBack stop", async () => {
    const prompt = String.raw`Why is $\frac{1}{2} + \frac{1}{4} = \frac{3}{4}$?`;
    const view = await render(<RelatedPromptLines prompts={[prompt, MATH]} onSelect={jest.fn()} />);
    expect(view.getAllByTestId("rich-math-body").length).toBeGreaterThan(0);
    expect(nestedAccessibleElements(view.toJSON())).toEqual([]);
  });
});

describe("RelatedPromptLines in other scripts", () => {
  it("offers follow-ups written in Russian, Amharic and French", async () => {
    const prompts = [
      "Какой рис лучше всего подходит для плова?",
      "ዶሮ ወጥ ምን ያህል ጊዜ ይበስላል?",
      "Combien de temps faut-il pétrir la pâte ?",
    ];
    const onSelect = jest.fn();
    const { getAllByRole, getByLabelText } = await render(
      <RelatedPromptLines prompts={prompts} onSelect={onSelect} />,
    );

    expect(getAllByRole("button")).toHaveLength(3);
    fireEvent.press(getByLabelText(prompts[1]!));
    expect(onSelect).toHaveBeenCalledWith(prompts[1]);
  });
});

describe("RelatedPromptLines underline", () => {
  it("draws dots across the words' width once it is measured", async () => {
    const { getByTestId } = await render(
      <RelatedPromptLines prompts={[PHYSICS]} onSelect={jest.fn()} />,
    );
    const underline = getByTestId("related-prompt-underline");
    await act(async () => {
      fireEvent(underline, "layout", { nativeEvent: { layout: { width: 50, height: 2 } } });
    });
    // 2pt dots, 3pt apart: 10 across 50pt.
    expect(underline.children).toHaveLength(10);
  });
});

describe("RelatedPromptLines maths before a question mark", () => {
  beforeEach(() => {
    jest.spyOn(Dimensions, "get").mockReturnValue({ width: 440, height: 956, scale: 3, fontScale: 1 });
  });
  afterEach(() => {
    jest.restoreAllMocks();
    cleanup();
  });

  // Drawn "What if v₀ = 15 m/s ?": the formula's box ran on past its glyphs.
  it.each([
    [String.raw`What if $v_0 = 15\text{ m/s}$?`, "What if v₀ = 15 m/s?"],
    [String.raw`How high does it go with $g = 9.81\text{ m/s}^2$?`, "How high does it go with g = 9.81 m/s²?"],
  ])("sets the mark against %s", async (prompt, line) => {
    const { getByTestId } = await render(<RelatedPromptLines prompts={[prompt]} onSelect={jest.fn()} />);
    expect(readLine(getByTestId("rich-math-body") as unknown as Element)).toBe(line);
  });
});
