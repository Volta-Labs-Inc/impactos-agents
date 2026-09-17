-- Submissions: a founder inserts and reads only their own company's rows, and
-- only as 'pending'; a founder can never update or delete. Staff/helper do
-- everything. Coach/advisor have no submission access at all.
begin;
select plan(11);

-- reads
set local role authenticated;
select set_config('request.jwt.claims', '{"sub":"11111111-0000-4000-8000-000000000001","role":"authenticated"}', true);
select is((select count(*)::int from public.submission), 3, 'staff reads every submission');
select set_config('request.jwt.claims', '{"sub":"11111111-0000-4000-8000-000000000004","role":"authenticated"}', true);
select is((select count(*)::int from public.submission), 0, 'coach reads no submissions');
select set_config('request.jwt.claims', '{"sub":"11111111-0000-4000-8000-000000000006","role":"authenticated"}', true);
select is((select count(*)::int from public.submission), 2, 'founder reads only their own company submissions');
select is((select count(*)::int from public.submission where company_id='22222222-0000-4000-8000-0000000000bb'), 0, 'founder reads no other company submission');
select set_config('request.jwt.claims', '{"sub":"11111111-0000-4000-8000-000000000003","role":"authenticated"}', true);
select is((select count(*)::int from public.submission), 0, 'ended helper reads no submissions');
reset role;

-- founder writes
set local role authenticated;
select set_config('request.jwt.claims', '{"sub":"11111111-0000-4000-8000-000000000006","role":"authenticated"}', true);
select lives_ok(
  $$insert into public.submission (source_system, source_id, company_id, channel, submitted_at, status)
     values ('t','founder-pending','22222222-0000-4000-8000-0000000000aa','hosted_form',current_date,'pending')$$,
  'founder can insert a pending submission for their own company');
select throws_ok(
  $$insert into public.submission (source_system, source_id, company_id, channel, submitted_at, status)
     values ('t','founder-accepted','22222222-0000-4000-8000-0000000000aa','hosted_form',current_date,'accepted')$$,
  '42501', NULL, 'founder cannot insert a non-pending submission');
select throws_ok(
  $$insert into public.submission (source_system, source_id, company_id, channel, submitted_at, status)
     values ('t','founder-other','22222222-0000-4000-8000-0000000000bb','hosted_form',current_date,'pending')$$,
  '42501', NULL, 'founder cannot insert a submission for another company');
update public.submission set status='accepted' where source_id='submission-a-pending';
select is(
  (select status from public.submission where source_id='submission-a-pending'),
  'pending', 'founder update leaves the submission unchanged');
delete from public.submission where source_id='submission-a-pending';
select is(
  (select count(*)::int from public.submission where source_id='submission-a-pending'),
  1, 'founder delete leaves the submission present');
reset role;

-- staff can update
set local role authenticated;
select set_config('request.jwt.claims', '{"sub":"11111111-0000-4000-8000-000000000001","role":"authenticated"}', true);
update public.submission set status='accepted' where source_id='submission-a-pending';
select is(
  (select status from public.submission where source_id='submission-a-pending'),
  'accepted', 'staff can update a submission');
reset role;

select * from finish();
rollback;
