# Reporting anchors

This document explains how the impactOS reporting profile
(`contract/reporting-profile.json`) supports the public frameworks it is built
from. It is **one iteration, a starting point** meant to help satisfy the needs
outlined in the cited documents. It is not a funder agreement and contains no
agreement text: each contribution differs, so this repository anchors only to
the public sources below. Organisations are expected to extend the profile for
their own funders.

Every field in the reporting profile names one **anchor** — the framework it
comes from. This document names each anchor and explains, in plain terms, what
the impactOS data contract collects so that anchor can be reported. If you add a
field to the profile, add its anchor here too; a test keeps the two in step.

## Why a profile, not a spreadsheet

The BAI spreadsheet is one government-approved configuration of a broader
direct-beneficiary reporting requirement. Anchoring to a versioned profile,
rather than to a single spreadsheet, lets an organisation report to more than
one funder and extend the field set without breaking the export. The spreadsheet
becomes one export mapping (`contract/exports/bai-template-v5.json`), not the
definition of the requirement.

## The anchors

### ISED BAI PMF

The **ISED BAI PMF** (Business Accelerator and Incubator Performance Measurement
Framework) company questionnaire is completed annually for each supported
company. It asks for the company's legal identity and age, its stage on a
growth scale, its industry, founder counts by demographic group, employee counts
inside and outside Canada (full- and part-time), annual and export revenue,
financing broken down by source, patents applied and granted, a net promoter
score and an impact rating.

How the contract supports it: company identity and age live on `company`;
employee counts, revenue, patents, NPS and impact rating live on
`company_update` at a dated grain; financing lives on `funding_event`, one row
per event, grouped by funding type; the growth stage is derived from a company's
position on its track (`milestone_position`) rolled up to a funder stage via
`tracks.json`. Founder demographics are recorded per person on
`person.demographics` and rolled up per company — never inferred.

Source:
<https://ised-isde.canada.ca/site/sme-research-statistics/en/business-accelerators-and-incubators/bai-performance-measurement-framework/business-accelerator-and-incubator-performance-measurement-survey>

### CED 2024-2028

The **CED 2024-2028** incubator and accelerator application guide (the RDA
performance grid) asks for outcomes across the whole portfolio: businesses
assisted, average coaching and mentoring hours per business, jobs created and
maintained, total sales, total and average funding received, and a survival
rate. This is the preferred primary anchor.

How the contract supports it: businesses assisted is a count of companies with a
cohort `membership`; coaching hours come from `interaction` records of
coaching sessions, divided by businesses assisted; jobs created and maintained
derive from full-time-equivalent employment (`company_update` and
`team_member_period`); total and average funding come from `funding_event`; total
sales come from revenue on `company_update`; the survival rate is derived from
companies still active over time.

Source:
<https://www.canada.ca/en/economic-development-quebec-regions/financing-services/support-for-quebecs-business-incubators-and-accelerators-call-for-proposals/ced-support-for-incubators-and-accelerators-2024-2028-application-guide.html>

### PacifiCan glossary

The **PacifiCan glossary** defines the terms funders use. Jobs created and
maintained are measured in full-time equivalents, and "maintained" means a job
that would be lost without the project. "Diverse groups" is defined as persons
with disabilities, Indigenous peoples, youth, immigrants, racialized people,
2SLGBTQ+ people, women, and official-language-minority communities.

How the contract supports it: the `diverse_groups` vocabulary in the data
contract is exactly this PacifiCan list, and it is recorded per person on
`person.demographics`, never on the company. The FTE definitions govern how jobs
created and maintained are counted.

Source:
<https://www.canada.ca/en/pacific-economic-development/services/funding/funding-program-glossary.html>

### BAI Template v5

The **BAI Template v5** workbook is the ACOA-approved configuration of this
reporting requirement, with a direct-beneficiary versus industry-partner split.
It is one export of the profile, mapped column by column in
`contract/exports/bai-template-v5.json`.

How the contract supports it: the export mapping links every workbook column to a
data-contract source. Where a workbook column has no contract source — for
example Cost of Support, which the contract does not collect — the mapping marks
it unmapped and records why, so the gap is explicit rather than silent.

## Fields that this iteration cannot yet fill

Reporting honestly means naming what is missing. In this first iteration:

- **Cost of Support** is not collected. It is derivable only from support time
  and advisor rates, which the contract does not carry, so it is left blank in
  the BAI export.
- **Street address** is not collected; only city and province are.
- Some funder demographic columns (for example the BAI split of Black
  Communities from Racialized) are narrower than the PacifiCan grouping the
  contract records, and are produced through a documented vocabulary crosswalk.

Each of these is a candidate for a later iteration once a first adopter's real
data shows whether it is needed.
