import { describe, expect, it } from "vitest";
import indexHtml from "../index.html?raw";
import faviconSvg from "../public/favicon.svg?raw";
import bseLogoSvg from "../public/brand/bse.svg?raw";

function parseSvg(source: string): SVGSVGElement {
  const doc = new DOMParser().parseFromString(source, "image/svg+xml");
  return doc.documentElement as unknown as SVGSVGElement;
}

function pathData(svg: Element): string[] {
  return Array.from(svg.querySelectorAll("path"), (path) => path.getAttribute("d") ?? "");
}

describe("browser tab icon", () => {
  it("is linked from index.html as /favicon.svg", () => {
    const doc = new DOMParser().parseFromString(indexHtml, "text/html");
    const icons = doc.querySelectorAll('link[rel="icon"]');
    expect(icons).toHaveLength(1);
    expect(icons[0]?.getAttribute("href")).toBe("/favicon.svg");
    expect(icons[0]?.getAttribute("type")).toBe("image/svg+xml");
  });

  it("is a square with the dark rounded background the white logo needs", () => {
    const favicon = parseSvg(faviconSvg);
    expect(favicon.getAttribute("viewBox")).toBe("0 0 64 64");
    const background = favicon.querySelector(":scope > rect");
    expect(background?.getAttribute("fill")).toBe("#08080A");
    expect(background?.getAttribute("width")).toBe("64");
    expect(background?.getAttribute("height")).toBe("64");
    expect(Number(background?.getAttribute("rx"))).toBeGreaterThan(0);
  });

  it("carries the BSE logo unstretched, centered inside padding", () => {
    const logo = parseSvg(faviconSvg).querySelector(":scope > svg");
    expect(logo?.getAttribute("viewBox")).toBe(parseSvg(bseLogoSvg).getAttribute("viewBox"));
    expect(logo?.getAttribute("preserveAspectRatio")).toBe("xMidYMid meet");
    const [x, y, width, height] = ["x", "y", "width", "height"].map((name) => Number(logo?.getAttribute(name)));
    expect(x).toBeGreaterThan(0);
    expect(x! + width!).toBe(64 - x!);
    expect(y! + height!).toBe(64 - y!);
    expect(pathData(logo!)).toEqual(pathData(parseSvg(bseLogoSvg)));
    expect(pathData(logo!)).not.toHaveLength(0);
  });
});
