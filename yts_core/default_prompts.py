SUMMARY_PROMPT = r'''
You are summarizing a YouTube transcript.

Return JSON only.

Important epistemic rule:
- Do not claim objective truth.
- Summarize what the transcript says.
- Treat product claims, political claims, forecasts, allegations, and future claims as claims in the source material.

Return exactly this JSON shape:
{
  "title": "short title",
  "sections": [
    {
      "section_id": "sec_001",
      "title": "section title",
      "items": [
        {
          "summary_item_id": "sum_001",
          "text": "one factual summary sentence or bullet"
        }
      ]
    }
  ],
  "tldr": ["short takeaway"]
}

Rules:
- Keep important names, dates, numbers, products, and comparisons.
- Prefer smaller summary items over long paragraphs.
- Each item should be understandable on its own.
- Do not use markdown.

TRANSCRIPT:
"""
{transcript}
"""
'''

CLAIM_COLLECTION_PROMPT = r'''
You are a claim extraction tool.

Extract factual claims from the SUMMARY JSON.

Rules:
- Return JSON only.
- Do not verify claims.
- Do not rewrite the summary.
- Extract claims that can be checked against a source transcript.
- Include attribution claims, such as "the speaker believes X" or "the speaker criticizes Y".
- If one summary item contains multiple factual claims, split them into separate claims.
- Use the provided summary_item_id values exactly.
- claim_source_text must be an exact substring copied from the summary item text.
- Do not invent character spans; include start_char/end_char only if you are certain. They may be null.

Return exactly this JSON shape:
{
  "claims": [
    {
      "summary_item_id": "sum_001",
      "claim": "claim text",
      "summary_context": "exact summary item text",
      "claim_source_text": "exact substring from summary_context",
      "claim_span": {"start_char": null, "end_char": null}
    }
  ]
}

SUMMARY JSON:
{summary_json}
'''

VERIFY_CLAIM_PROMPT = r'''
You are NOT a summarizer.
You are NOT allowed to summarize the transcript.

Your task is to verify exactly ONE CLAIM against the FULL TRANSCRIPT.

Important epistemic rule:
These labels only describe the relationship between the claim and the transcript.
They do not say whether the claim is objectively true in the real world.

Allowed transcript_relationship values:
- FOUND_SUPPORTING_EVIDENCE
- FOUND_CONTRADICTING_EVIDENCE
- NO_SUPPORTING_EVIDENCE_FOUND
- UNCLEAR_FROM_TRANSCRIPT

CLAIM JSON:
{claim_json}

Return JSON only with exactly these keys:
{
  "claim": "claim text",
  "transcript_relationship": "FOUND_SUPPORTING_EVIDENCE",
  "reason": "brief reason with short supporting evidence",
  "suggested_fix": ""
}

Rules:
- Verify only the claim above.
- Do not summarize the transcript.
- Do not create a transcript breakdown.
- Do not use the key "transcript".
- Discussion of a claim does not mean endorsement.
- Reporting another person's view does not mean the speaker believes it.
- Criticizing a claim does not mean supporting it.
- If attribution is wrong, use FOUND_CONTRADICTING_EVIDENCE or UNCLEAR_FROM_TRANSCRIPT.
- If the transcript discusses the topic but does not support the exact claim, use UNCLEAR_FROM_TRANSCRIPT.
- If the transcript does not mention the topic at all, use NO_SUPPORTING_EVIDENCE_FOUND.
- If supported, include a brief quotation or paraphrase from the transcript in the reason.

FULL TRANSCRIPT:
"""
{transcript}
"""
'''

ANNOTATION_PROMPT = r'''
You are an evidence annotation tool.

Your job is not to rewrite the summary and not to decide objective truth.
Your job is to mark which summary claims should be read more carefully based on transcript relationship results.

Input contains summary items, claims, and verifications.

Return JSON only with this shape:
{
  "annotations": [
    {
      "summary_item_id": "sum_001",
      "claim_id": "claim_001",
      "evidence_strength": "strong|partial|missing|contradicted|unclear",
      "display_risk": "normal|caution|review",
      "reason": "short UI-friendly explanation"
    }
  ]
}

Mapping guidance:
- FOUND_SUPPORTING_EVIDENCE => evidence_strength strong, display_risk normal
- FOUND_CONTRADICTING_EVIDENCE => evidence_strength contradicted, display_risk review
- NO_SUPPORTING_EVIDENCE_FOUND => evidence_strength missing, display_risk review
- UNCLEAR_FROM_TRANSCRIPT => evidence_strength unclear, display_risk caution

Remember:
- Do not say the claim is true or false.
- Say only how well the transcript supports it.

INPUT JSON:
{annotation_input_json}
'''
