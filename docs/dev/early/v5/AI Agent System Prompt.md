# **Repo2Gal - AI Agent System Prompt & Coding Guidelines**

**Target Audience**: AI Coding Assistants (Cursor, Windsurf, Claude Dev, etc.)  
**Project Goal**: Transform GitHub repositories into interactive Visual Novel presentations (WebGAL) via a pure Python pipeline.  
**Core Philosophy**: Low complexity for V1, strict schema-driven contexts, robust DSL compilation, high modularity.

## **1. Project Context & Objectives**

### **1.1 Product Definition**

**Repo2Gal** is an automated Python tool that converts a GitHub repository into an **Interactive Anime Documentation (Visual Novel Presentation)** powered by WebGAL.  
It does **NOT** attempt to build a complex RPG. It reimagines README.md into an engaging, playable story with repository personification (Repo-chan).

### **1.2 Core Modes**

> 1. **Explorer Mode (探索模式)**: Overview of repository features, usage, and value proposition (Source: README, package.json/configs).  
> 2. **Architect Mode (架构模式)**: In-depth walk-through of file structure and core API modules for developers (Source: File tree, core source files).  
> 3. **Chronicle Mode (编年模式)**: Historical narrative of major milestones, issues, and contributor evolution (Source: Git commits, major PRs/Issues).

## **2. Technical Stack & Dependencies**

> * **Language**: Python 3.10+  
> * **Data Extractor**:  
  * donoceidon/repo2txt (Extract directory structure & core code)  
  * Oltrematica/github_analyzer or Git CLI (Extract commits & history)  
> * **AI / LLM Framework**: pydantic/pydantic-ai or google-genai / openai with strict Pydantic structured output.  
> * **Delivery Target**: OpenWebGAL/WebGAL (HTML/JS Web-based VN Engine). The compiler outputs WebGAL .txt scripts and asset configurations into a ./output/<repo_name>_gal/ directory.

## **3. System Architecture & Pipeline**

[GitHub Repo / Local Path]  
          │  
          ▼  
┌─────────────────────────┐  
│ 1. Data Extractor       │  (Fetch Raw Files / Git History)  
└──────────┬──────────────┘  
          │  
          ▼  
┌─────────────────────────┐  
│ 2. Context Builder      │  (Distill raw data into structured JSON Context)  
└──────────┬──────────────┘  
          │  
          ▼  
┌─────────────────────────┐  
│ 3. Story Generator      │  (LLM generates Markdown/DSL Script based on Context)  
└──────────┬──────────────┘  
          │  
          ▼  
┌─────────────────────────┐  
│ 4. DSL Compiler         │  (Line-by-line Regex/Parser converting DSL to WebGAL commands)  
└──────────┬──────────────┘  
          │  
          ▼  
┌─────────────────────────┐  
│ 5. Delivery Packager    │  (Output WebGAL ready folder structure)  
└─────────────────────────┘

## **4. Directory Structure (Strict Protocol)**

All code must adhere to the following project structure:  
repo2gal/  
├── config/  
│   └── western_fantasy.json    # Mapping table for backgrounds, characters, placeholder assets  
├── src/  
│   ├── __init__.py  
│   ├── extractor/              # Raw data fetching  
│   │   ├── github.py           # GitHub API / local git fetcher  
│   │   └── filesystem.py       # File tree and code extractor  
│   ├── context/                # Context Builder (Pydantic Models)  
│   │   ├── schema.py           # Pydantic data schemas  
│   │   └── builder.py          # Distillation logic (Raw -> Context JSON)  
│   ├── generator/              # LLM Story Generator  
│   │   ├── prompts.py          # System prompts for 3 modes & Repo Persona  
│   │   └── llm.py              # LLM invocation logic  
│   ├── compiler/               # DSL to WebGAL Parser  
│   │   ├── parser.py           # Markdown/DSL parser  
│   │   └── webgal.py           # WebGAL syntax emitter  
│   └── delivery/               # Packaging & Asset assembly  
│       └── packager.py  
├── output/                     # Export directory  
├── main.py                     # CLI entry point (Typer / Argparse)  
├── pyproject.toml  
└── README.md

## **5. Data & DSL Protocol Specifications**

### **5.1 Context Schema (src/context/schema.py)**

AI Agent **MUST** use Pydantic models for structured context distillation:  
from pydantic import BaseModel  
from typing import List, Optional

class RepoIdentity(BaseModel):  
    name: str  
    description: str  
    primary_language: str  
    persona_traits: List[str]  # e.g., ["Fast", "Elegant", "Type-Safe"]

class ArchitectureNode(BaseModel):  
    module_name: str  
    filepath: str  
    responsibility: str

class HistoricalEvent(BaseModel):  
    date: str  
    event_type: str  # "feature", "bugfix", "breaking_change"  
    description: str

class RepoContext(BaseModel):  
    identity: RepoIdentity  
    architecture: List[ArchitectureNode]  
    history: List[HistoricalEvent]  
    readme_summary: str

### **5.2 Markdown Script DSL Specification**

The Story Generator LLM **MUST ONLY** output the following Markdown-based DSL. Do **NOT** generate JSON for scripts to avoid syntax errors.  
**DSL Rules**:

> 1. [场景: <scene_id>] -> Scene/Background switch  
> 2. [BGM: <bgm_id>] -> Background Music switch  
> 3. [旁白: <text>] -> Narrator text  
> 4. **<Character_Name>** (<Emotion>): <Dialogue_Text> -> Character dialogue  
> 5. > <Option_Text> -> [<Target_Scene>] -> Choice option

**DSL Sample**:  
[场景: 魔法高塔]  
[BGM: 轻松日常]  
[旁白: 圣物精灵缓缓抚摸着古老的光符，魔法阵随之亮起。]

**Repo娘** (开心): 欢迎来到我的核心领地！在这里，所有的状态变化都是响应式的哦。  
**骑士** (疑惑): 可是，如果数据层级太深，你的魔法还能保持优雅吗？

> 选项 A：查看响应式原理 -> [场景: 架构详解]  
> 选项 B：查看安装方法 -> [场景: 快速入手]

### **5.3 WebGAL Target Output (src/compiler/webgal.py)**

The Compiler parses the DSL into WebGAL .txt script commands:  
changeBg:assets/bg/tower.jpg;  
bgm:assets/bgm/daily.mp3;  
圣物精灵缓缓抚摸着古老的光符，魔法阵随之亮起。;  
Repo娘:欢迎来到我的核心领地！在这里，所有的状态变化都是响应式的哦。;  
骑士:可是，如果数据层级太深，你的魔法还能保持优雅吗？;

## **6. Guidelines for AI Agent Development**

When writing or editing code for this project, the AI Agent must strictly follow these directives:

### **🎯 Rule 1: No Over-engineering**

> * Do **NOT** implement complex Agentic Tool-Calling loops in V1. Use Context Builder -> LLM Single Pass -> Compiler.  
> * Do **NOT** write heavy AST compilers with lark or ply. Use clean, robust line-by-line Regex parsing for the DSL.

### **🛡️ Rule 2: Robust Error Handling (Fallback Mechanism)**

> * If the DSL Parser encounters a line it cannot parse as character dialogue or command, **fallback to treating it as Narrator text ([旁白])**.  
> * **NEVER** throw an unhandled exception during compilation that stops the build pipeline.

### **📦 Rule 3: Decouple Engine Assets**

> * Do not hardcode image paths inside the LLM prompt or compiler.  
> * Use config/western_fantasy.json to map high-level identifiers (魔法高塔) to real asset paths (assets/bg/tower.jpg).

### **🐍 Rule 4: Clean Pythonic Code**

> * Use Type Hints everywhere (typing.List, typing.Dict, typing.Optional).  
> * Keep function size small (< 50 lines).  
> * Make functions easily testable with pytest.

## **7. Step-by-Step Task Execution Order for Vibe Coding**

When instructed to implement features, execute in the following order:

> 1. **Step 1**: Implement src/context/schema.py and src/context/builder.py to convert raw repository files into RepoContext.  
> 2. **Step 2**: Implement src/compiler/parser.py and webgal.py to ensure Markdown DSL can be correctly converted into WebGAL commands.  
> 3. **Step 3**: Write System Prompts in src/generator/prompts.py for the 3 modes & Persona generator.  
> 4. **Step 4**: Implement src/generator/llm.py to trigger LLM calls using the RepoContext.  
> 5. **Step 5**: Implement src/delivery/packager.py to copy static templates and write output .txt files into ./output/.  
> 6. **Step 6**: Implement main.py CLI interface using typer or argparse.