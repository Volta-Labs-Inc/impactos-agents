-- impactOS store seed: milestone tracks and rungs.
-- Generated from contract/tracks.json (system tracks, D-07). Idempotent.
-- Regenerate with: python3 store/seed/generate_tracks.py > store/seed/tracks.sql

insert into public.milestone_track (slug, name, description)
values ('software', 'Software', 'Software company progression from validated problem to product-market fit.')
on conflict (slug) do update set name = excluded.name, description = excluded.description, updated_at = now();

insert into public.milestone_track (slug, name, description)
values ('hardware', 'Hardware', 'Hardware company progression from validated problem to market adoption.')
on conflict (slug) do update set name = excluded.name, description = excluded.description, updated_at = now();

insert into public.milestone_track (slug, name, description)
values ('medical_device', 'Medical Device', 'Medical device progression from validated clinical need to scaled adoption.')
on conflict (slug) do update set name = excluded.name, description = excluded.description, updated_at = now();

insert into public.milestone_track (slug, name, description)
values ('biotech_pharma', 'Biotech/Pharma', 'Biotech and pharma progression from preclinical validation to commercial launch.')
on conflict (slug) do update set name = excluded.name, description = excluded.description, updated_at = now();

insert into public.milestone_definition (track_id, rung_order, name, evidence_description, objective_signal, funder_stage)
select mt.id, 1, 'Problem Validated', 'Interviews and research confirm a real, prioritised problem for a defined customer.', 'Documented problem statement with corroborating customer interviews.', 'Idea'
from public.milestone_track mt where mt.slug = 'software'
on conflict (track_id, rung_order) do update set name = excluded.name, evidence_description = excluded.evidence_description, objective_signal = excluded.objective_signal, funder_stage = excluded.funder_stage, updated_at = now();

insert into public.milestone_definition (track_id, rung_order, name, evidence_description, objective_signal, funder_stage)
select mt.id, 2, 'Solution Validated', 'Prospective customers confirm the proposed solution addresses the problem.', 'Positive solution-validation interviews or a signed letter of intent.', 'MVP'
from public.milestone_track mt where mt.slug = 'software'
on conflict (track_id, rung_order) do update set name = excluded.name, evidence_description = excluded.evidence_description, objective_signal = excluded.objective_signal, funder_stage = excluded.funder_stage, updated_at = now();

insert into public.milestone_definition (track_id, rung_order, name, evidence_description, objective_signal, funder_stage)
select mt.id, 3, 'First Paying Customer', 'A customer pays for the product.', 'First closed-won paid contract or transaction.', 'Early Adopters'
from public.milestone_track mt where mt.slug = 'software'
on conflict (track_id, rung_order) do update set name = excluded.name, evidence_description = excluded.evidence_description, objective_signal = excluded.objective_signal, funder_stage = excluded.funder_stage, updated_at = now();

insert into public.milestone_definition (track_id, rung_order, name, evidence_description, objective_signal, funder_stage)
select mt.id, 4, 'Repeatable Sales with ICP', 'Sales repeat within a defined ideal customer profile with healthy conversion.', 'About $10K MRR/monthly revenue at roughly 40% win rate within the ICP.', 'Growth'
from public.milestone_track mt where mt.slug = 'software'
on conflict (track_id, rung_order) do update set name = excluded.name, evidence_description = excluded.evidence_description, objective_signal = excluded.objective_signal, funder_stage = excluded.funder_stage, updated_at = now();

insert into public.milestone_definition (track_id, rung_order, name, evidence_description, objective_signal, funder_stage)
select mt.id, 5, 'Early Product-Market Fit', 'Retention and demand indicate early product-market fit.', 'About $100K revenue with roughly 60% retention or repeat purchase.', 'Growth'
from public.milestone_track mt where mt.slug = 'software'
on conflict (track_id, rung_order) do update set name = excluded.name, evidence_description = excluded.evidence_description, objective_signal = excluded.objective_signal, funder_stage = excluded.funder_stage, updated_at = now();

insert into public.milestone_definition (track_id, rung_order, name, evidence_description, objective_signal, funder_stage)
select mt.id, 6, 'Product-Market Fit', 'Durable demand and retention at scale.', 'About $1M revenue with roughly 80% retention.', 'Scale'
from public.milestone_track mt where mt.slug = 'software'
on conflict (track_id, rung_order) do update set name = excluded.name, evidence_description = excluded.evidence_description, objective_signal = excluded.objective_signal, funder_stage = excluded.funder_stage, updated_at = now();

insert into public.milestone_definition (track_id, rung_order, name, evidence_description, objective_signal, funder_stage)
select mt.id, 1, 'Problem Validated', 'Research confirms a real, prioritised problem for a defined customer.', 'Documented problem statement with corroborating customer interviews.', 'Idea'
from public.milestone_track mt where mt.slug = 'hardware'
on conflict (track_id, rung_order) do update set name = excluded.name, evidence_description = excluded.evidence_description, objective_signal = excluded.objective_signal, funder_stage = excluded.funder_stage, updated_at = now();

insert into public.milestone_definition (track_id, rung_order, name, evidence_description, objective_signal, funder_stage)
select mt.id, 2, 'Proof of Concept Built', 'A working proof of concept demonstrates technical feasibility.', 'Functioning bench prototype demonstrating the core mechanism.', 'MVP'
from public.milestone_track mt where mt.slug = 'hardware'
on conflict (track_id, rung_order) do update set name = excluded.name, evidence_description = excluded.evidence_description, objective_signal = excluded.objective_signal, funder_stage = excluded.funder_stage, updated_at = now();

insert into public.milestone_definition (track_id, rung_order, name, evidence_description, objective_signal, funder_stage)
select mt.id, 3, 'User-Validated MVP', 'A minimum viable product is tested and validated with users.', 'Users complete the core task with a working MVP and confirm value.', 'MVP'
from public.milestone_track mt where mt.slug = 'hardware'
on conflict (track_id, rung_order) do update set name = excluded.name, evidence_description = excluded.evidence_description, objective_signal = excluded.objective_signal, funder_stage = excluded.funder_stage, updated_at = now();

insert into public.milestone_definition (track_id, rung_order, name, evidence_description, objective_signal, funder_stage)
select mt.id, 4, 'Pilot Production and First Customers', 'Pilot-scale production delivers units to first paying customers.', 'Pilot run shipped; first customers paying for units.', 'Early Adopters'
from public.milestone_track mt where mt.slug = 'hardware'
on conflict (track_id, rung_order) do update set name = excluded.name, evidence_description = excluded.evidence_description, objective_signal = excluded.objective_signal, funder_stage = excluded.funder_stage, updated_at = now();

insert into public.milestone_definition (track_id, rung_order, name, evidence_description, objective_signal, funder_stage)
select mt.id, 5, 'Mass Production Ready', 'Design and supply chain are ready for volume manufacturing.', 'Design-for-manufacture complete; contract manufacturer secured.', 'Growth'
from public.milestone_track mt where mt.slug = 'hardware'
on conflict (track_id, rung_order) do update set name = excluded.name, evidence_description = excluded.evidence_description, objective_signal = excluded.objective_signal, funder_stage = excluded.funder_stage, updated_at = now();

insert into public.milestone_definition (track_id, rung_order, name, evidence_description, objective_signal, funder_stage)
select mt.id, 6, 'Early Traction', 'Sales demonstrate early market traction.', 'About $100K in cumulative sales.', 'Growth'
from public.milestone_track mt where mt.slug = 'hardware'
on conflict (track_id, rung_order) do update set name = excluded.name, evidence_description = excluded.evidence_description, objective_signal = excluded.objective_signal, funder_stage = excluded.funder_stage, updated_at = now();

insert into public.milestone_definition (track_id, rung_order, name, evidence_description, objective_signal, funder_stage)
select mt.id, 7, 'Market Validation', 'Sustained sales validate the market.', 'About $1M in sales.', 'Scale'
from public.milestone_track mt where mt.slug = 'hardware'
on conflict (track_id, rung_order) do update set name = excluded.name, evidence_description = excluded.evidence_description, objective_signal = excluded.objective_signal, funder_stage = excluded.funder_stage, updated_at = now();

insert into public.milestone_definition (track_id, rung_order, name, evidence_description, objective_signal, funder_stage)
select mt.id, 8, 'Market Adoption', 'Broad market adoption at scale.', 'About $10M in sales.', 'Scale'
from public.milestone_track mt where mt.slug = 'hardware'
on conflict (track_id, rung_order) do update set name = excluded.name, evidence_description = excluded.evidence_description, objective_signal = excluded.objective_signal, funder_stage = excluded.funder_stage, updated_at = now();

insert into public.milestone_definition (track_id, rung_order, name, evidence_description, objective_signal, funder_stage)
select mt.id, 1, 'Clinical Need Validated', 'The clinical need and target use are validated with clinicians.', 'Documented clinical need with clinician corroboration.', 'Idea'
from public.milestone_track mt where mt.slug = 'medical_device'
on conflict (track_id, rung_order) do update set name = excluded.name, evidence_description = excluded.evidence_description, objective_signal = excluded.objective_signal, funder_stage = excluded.funder_stage, updated_at = now();

insert into public.milestone_definition (track_id, rung_order, name, evidence_description, objective_signal, funder_stage)
select mt.id, 2, 'Prototype Validated (ISO 14971)', 'A prototype is validated with risk management per ISO 14971.', 'Validated prototype with an ISO 14971 risk file.', 'MVP'
from public.milestone_track mt where mt.slug = 'medical_device'
on conflict (track_id, rung_order) do update set name = excluded.name, evidence_description = excluded.evidence_description, objective_signal = excluded.objective_signal, funder_stage = excluded.funder_stage, updated_at = now();

insert into public.milestone_definition (track_id, rung_order, name, evidence_description, objective_signal, funder_stage)
select mt.id, 3, 'Clinical Evidence', 'Clinical study generates evidence of safety and performance.', 'Completed clinical study with reported outcomes.', 'Early Adopters'
from public.milestone_track mt where mt.slug = 'medical_device'
on conflict (track_id, rung_order) do update set name = excluded.name, evidence_description = excluded.evidence_description, objective_signal = excluded.objective_signal, funder_stage = excluded.funder_stage, updated_at = now();

insert into public.milestone_definition (track_id, rung_order, name, evidence_description, objective_signal, funder_stage)
select mt.id, 4, 'Regulatory Clearance', 'The device receives regulatory clearance or approval to market.', 'Health Canada / FDA clearance or approval obtained.', 'Growth'
from public.milestone_track mt where mt.slug = 'medical_device'
on conflict (track_id, rung_order) do update set name = excluded.name, evidence_description = excluded.evidence_description, objective_signal = excluded.objective_signal, funder_stage = excluded.funder_stage, updated_at = now();

insert into public.milestone_definition (track_id, rung_order, name, evidence_description, objective_signal, funder_stage)
select mt.id, 5, 'Reimbursement Validated', 'Payers reimburse the device.', 'Reimbursement pathway confirmed with a payer.', 'Growth'
from public.milestone_track mt where mt.slug = 'medical_device'
on conflict (track_id, rung_order) do update set name = excluded.name, evidence_description = excluded.evidence_description, objective_signal = excluded.objective_signal, funder_stage = excluded.funder_stage, updated_at = now();

insert into public.milestone_definition (track_id, rung_order, name, evidence_description, objective_signal, funder_stage)
select mt.id, 6, 'Market Adoption', 'Adoption generates meaningful revenue.', 'About $1M in revenue.', 'Scale'
from public.milestone_track mt where mt.slug = 'medical_device'
on conflict (track_id, rung_order) do update set name = excluded.name, evidence_description = excluded.evidence_description, objective_signal = excluded.objective_signal, funder_stage = excluded.funder_stage, updated_at = now();

insert into public.milestone_definition (track_id, rung_order, name, evidence_description, objective_signal, funder_stage)
select mt.id, 7, 'Scaled Adoption', 'Adoption scales across sites and geographies.', 'About $10M in revenue.', 'Scale'
from public.milestone_track mt where mt.slug = 'medical_device'
on conflict (track_id, rung_order) do update set name = excluded.name, evidence_description = excluded.evidence_description, objective_signal = excluded.objective_signal, funder_stage = excluded.funder_stage, updated_at = now();

insert into public.milestone_definition (track_id, rung_order, name, evidence_description, objective_signal, funder_stage)
select mt.id, 1, 'Preclinical Validation', 'Preclinical studies validate the candidate.', 'Positive preclinical results supporting progression.', 'Idea'
from public.milestone_track mt where mt.slug = 'biotech_pharma'
on conflict (track_id, rung_order) do update set name = excluded.name, evidence_description = excluded.evidence_description, objective_signal = excluded.objective_signal, funder_stage = excluded.funder_stage, updated_at = now();

insert into public.milestone_definition (track_id, rung_order, name, evidence_description, objective_signal, funder_stage)
select mt.id, 2, 'Safety in Humans', 'Early-phase trials demonstrate safety in humans.', 'Phase 1 safety demonstrated.', 'MVP'
from public.milestone_track mt where mt.slug = 'biotech_pharma'
on conflict (track_id, rung_order) do update set name = excluded.name, evidence_description = excluded.evidence_description, objective_signal = excluded.objective_signal, funder_stage = excluded.funder_stage, updated_at = now();

insert into public.milestone_definition (track_id, rung_order, name, evidence_description, objective_signal, funder_stage)
select mt.id, 3, 'Efficacy Demonstrated', 'Mid-phase trials demonstrate efficacy.', 'Phase 2 efficacy signal demonstrated.', 'Early Adopters'
from public.milestone_track mt where mt.slug = 'biotech_pharma'
on conflict (track_id, rung_order) do update set name = excluded.name, evidence_description = excluded.evidence_description, objective_signal = excluded.objective_signal, funder_stage = excluded.funder_stage, updated_at = now();

insert into public.milestone_definition (track_id, rung_order, name, evidence_description, objective_signal, funder_stage)
select mt.id, 4, 'Confirmatory Evidence', 'Late-phase trials confirm efficacy and safety.', 'Phase 3 confirmatory results.', 'Growth'
from public.milestone_track mt where mt.slug = 'biotech_pharma'
on conflict (track_id, rung_order) do update set name = excluded.name, evidence_description = excluded.evidence_description, objective_signal = excluded.objective_signal, funder_stage = excluded.funder_stage, updated_at = now();

insert into public.milestone_definition (track_id, rung_order, name, evidence_description, objective_signal, funder_stage)
select mt.id, 5, 'Regulatory Approval', 'The therapy receives regulatory approval.', 'Regulatory approval obtained.', 'Growth'
from public.milestone_track mt where mt.slug = 'biotech_pharma'
on conflict (track_id, rung_order) do update set name = excluded.name, evidence_description = excluded.evidence_description, objective_signal = excluded.objective_signal, funder_stage = excluded.funder_stage, updated_at = now();

insert into public.milestone_definition (track_id, rung_order, name, evidence_description, objective_signal, funder_stage)
select mt.id, 6, 'Commercial Launch', 'The therapy is launched commercially at scale.', 'About $10M+ in revenue from commercial launch.', 'Scale'
from public.milestone_track mt where mt.slug = 'biotech_pharma'
on conflict (track_id, rung_order) do update set name = excluded.name, evidence_description = excluded.evidence_description, objective_signal = excluded.objective_signal, funder_stage = excluded.funder_stage, updated_at = now();

