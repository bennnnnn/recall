import { matchParts } from "@/features/search/model/matchParts";

it.each([
  ["How rainbows form", "rain", [["How ", false], ["rain", true], ["bows form", false]]],
  ["Acid Rain and rain", " RAIN ", [["Acid ", false], ["Rain", true], [" and ", false], ["rain", true]]],
  ["rain", "rain", [["rain", true]]],
  ["Train speeds", "speeds", [["Train ", false], ["speeds", true]]],
  ["Weather today", "rain", [["Weather today", false]]],
  ["Anything", "  ", [["Anything", false]]],
  ["İstanbul rain", "rain", [["İstanbul rain", false]]],
])("cuts %j where %j matched", (text, query, expected) => {
  expect(matchParts(text, query).map((part) => [part.text, part.match])).toEqual(expected);
});
