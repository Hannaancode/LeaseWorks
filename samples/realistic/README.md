# Lease evaluation sources

I use four original public lease templates from Qatar, Dubai and Queensland to test real PDF layouts, missing information and form fields. `public_sources.json` records publisher URLs and exact SHA-256 fingerprints. The opt-in evaluation runner downloads them into ignored temporary test storage; I do not relicense or redistribute the publishers' PDFs.

The Qatar Manateq document is a commercial plot lease, and the QSTP document is a commercial free-zone lease. They are not residential standard forms. The Dubai and Queensland documents are blank tenancy forms. A blank signature label is never evidence of signing. The QSTP file has 49 pages and deliberately exercises the documented 30-page ingestion limit.

I also complete a copy of the original Queensland form with fictional parties, amounts and dates, leaving signatures blank. That tests the actual interactive PDF structure without using private tenants' data. The TXT examples in this folder are author-created fictional Qatar residential, bilingual, quarterly, currency-conflict, unmatched-unit and US periodic scenarios. They are not official forms, executed contracts or legal advice.

The supplied owner rules and unit register apply to every test unchanged. A foreign or unmatched unit must remain unmatched; a weekly or periodic tenancy must preserve missing monthly/annual/fixed-term values rather than fabricate them to pass the policy.
