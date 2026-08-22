import {
  parseLearningLaunch,
  stripLearningLaunchBlock,
} from "@/lib/parseLearningLaunch";

const PROJECT_ID = "11111111-1111-4111-8111-111111111111";

describe("parseLearningLaunch", () => {
  it("reads a valid fence and ignores invented ids", () => {
    expect(
      parseLearningLaunch(
        `Let's practice.\n\`\`\`learning_launch\n{"project_id":"${PROJECT_ID}","action":"start"}\n\`\`\``,
      ),
    ).toEqual({ projectId: PROJECT_ID, action: "start" });
    expect(
      parseLearningLaunch('```learning_launch\n{"project_id":"not-a-uuid","action":"continue"}\n```'),
    ).toBeNull();
  });

  it("strips the fence from assistant prose", () => {
    expect(
      stripLearningLaunchBlock(`Ready when you are.\n\`\`\`learning_launch\n{"project_id":"${PROJECT_ID}"}\n\`\`\``),
    ).toBe("Ready when you are.");
  });
});
