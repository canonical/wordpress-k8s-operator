---
name: landing-page-helper
description: To create or update documentation landing pages that organize content by functional domains, ensuring a professional, balanced aesthetic while adhering to the Diataxis framework.
---

# Landing Page Helper Skill

## Purpose
To create or update documentation landing pages that organize content by functional domains, ensuring a professional, balanced aesthetic while adhering to the Diataxis framework.

## Core Principles
1.  **Domain-First Organization:** Organize files by their technical domain or functional theme (e.g., Networking, Security, Data Schema). 
2.  **Avoid Silos:** Do not organize by user persona (e.g., "For Beginners") or user journey (e.g., "Getting Started").
3.  **The Rule of Two:** A section header must contain at least two documents. If a theme only has one document, it must be merged into a broader related theme.
4.  **Aesthetic Pragmatism:** * If a Diataxis category contains **5 or more files**, use a **Structured** layout with section headers and descriptive text.
    * If a Diataxis category contains **fewer than 5 files**, use a **Flat** layout (simple directory).

---

## Technical Instructions

### Step 1: Diataxis Categorization
Identify which of the four Diataxis quadrants the documents belong to. Each landing page should focus on one quadrant:
* **Tutorials:** Learning-oriented.
* **How-to Guides:** Task-oriented.
* **Reference:** Information-oriented.
* **Explanation:** Understanding-oriented.

### Step 2: Workflow Selection (Audit vs. Creation)
Determine if a landing page (e.g., `index.md`) already exists for this category.

#### If the page exists (Audit Workflow):
1.  **Respect Existing Taxonomy:** If the current domains are functional and thematic, do not rename them unless they violate the "Rule of Two."
2.  **Identify Content Gaps:** Compare the local file list against the existing links. Integrate any "orphan" files into existing domains or create new ones if the Rule of Two is met.
3.  **The "Naked List" Fix:** If a section header is followed immediately by a list of links with no context, you **must** write a **Section Narrative** (see Step 4).

#### If the page does not exist (Creation Workflow):
1.  **Check Count:** If there are < 5 files, create a Flat layout. If ≥ 5, create a Structured layout.
2.  **Cluster Domains:** Group files into functional domains.
3.  **Apply Fallbacks:** Use the designated fallback category only as a last resort for files that cannot be grouped.

### Step 3: Fallback Categories
When the Rule of Two cannot be met through logical merging, use these specific fallback headers:
* **How-to Guides:** "Advanced operations"
* **Tutorials:** "Advanced tutorials"
* **Reference:** "Advanced topics"
* **Explanation:** "Conceptual deep-dives"

### Step 4: Content Generation
Regardless of layout or workflow, ensure the following elements are present:

1.  **Category Description:** A high-level overview of the category’s purpose (e.g., "These guides accompany you through the operations lifecycle...").
2.  **User Value Assessment:** A brief (1–2 sentence) summary of what the user can expect to achieve or learn from this documentation set.
3.  **Section Narratives (Structured Layout Only):** For every domain header, write 1–2 sentences of context. Explain *why* these tasks/items are grouped and their significance to the product.
4.  **Strategic Guidance:** If a section contains multiple competing options (e.g., two different deployment methods), add a sentence advising the user on how to choose between them.

---

## Content Mapping Reference Table

| Diataxis Type | Domain Style | Fallback Category (Last Resort) |
| :--- | :--- | :--- |
| **Tutorials** | Educational/Module-based | Advanced tutorials |
| **How-to Guides** | Functional/Task-based | Advanced operations |
| **Reference** | Technical/Machinery-based | Advanced topics |
| **Explanation** | Conceptual/Architectural | Conceptual deep-dives |