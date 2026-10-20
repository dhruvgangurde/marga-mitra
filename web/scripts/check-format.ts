// Run with: node --experimental-strip-types scripts/check-format.ts
import assert from 'node:assert/strict';
import {
  actorLabel, aqiBand, compareLabel, dateTimeLabel, dayDate, dayLabel, dayRange, deptName, errorText, inr,
  linkLabel, methodLabel, metres, metricDelta, recipientLabel, shortTime, signedInr, START_DATE, timeLabel, TODAY_DAY,
  workStatusBadge,
} from '../src/api/format.ts';

// money
assert.equal(inr(240000), '₹2,40,000');
assert.equal(inr(950), '₹950');
assert.equal(inr(-1640000), '\u2212₹16,40,000');
assert.equal(signedInr(38000), '+₹38,000');
assert.equal(signedInr(-164000), '\u2212₹1,64,000');
assert.equal(signedInr(0), '+₹0');

// days
assert.equal(START_DATE, '2026-11-02');
assert.equal(TODAY_DAY, 8);
assert.equal(dayDate(0).toISOString().slice(0, 10), '2026-11-02');
assert.equal(dayLabel(8), '10 Nov');
assert.equal(dayRange(8, 13), '10\u201315 Nov');
assert.equal(dayRange(18, 18), '20 Nov');
assert.equal(dayRange(26, 30), '28 Nov \u2013 2 Dec');

// clock times in IST
assert.equal(timeLabel('2026-11-10T10:02:11+05:30'), '10:02:11');
assert.equal(timeLabel('2026-11-10T04:32:11Z'), '10:02:11');
assert.equal(shortTime('2026-11-10T10:02:11+05:30'), '10:02');
assert.equal(dateTimeLabel('2026-10-26T17:40:00+05:30'), '26 Oct, 17:40');

// lengths and links
assert.equal(metres(620), '620 m');
assert.equal(metres(1100), '1.1 km');
assert.equal(linkLabel('9c1e' + '0'.repeat(56) + '44ab'), '9c1e…44ab');

// names
const depts: [string, string][] = [
  ['water', 'Water'], ['drainage', 'Drainage'], ['gas', 'Gas'], ['power', 'Power'], ['telecom', 'Telecom'],
  ['roads', 'Roads'], ['coordinator', 'Coordinator'], ['solver', 'Scheduler'],
];
for (const [id, name] of depts) assert.equal(deptName(id), name);

const actors: [string, string][] = [
  ['scheduler', 'Scheduler'], ['rules', 'Rules check'], ['ward_engineer', 'Ward engineer'],
  ['department_officer', 'Department officer'], ['forecast', 'Forecast check'], ['photo_check', 'Photo check'],
  ['resident', 'Resident'], ['auditor', 'Auditor'], ['coordinator', 'Coordinator'], ['system', 'MargaMitra'],
  ['gas', 'Gas'], ['someone_else', 'someone_else'],
];
for (const [id, name] of actors) assert.equal(actorLabel(id), name);

assert.equal(methodLabel('open_cut'), 'open cut');
assert.equal(methodLabel('trenchless'), 'trenchless');

const bands: [number, string][] = [
  [50, 'Good'], [88, 'Satisfactory'], [100, 'Satisfactory'], [200, 'Moderate'], [205, 'Poor'],
  [300, 'Poor'], [400, 'Very poor'], [401, 'Severe'],
];
for (const [aqi, band] of bands) assert.equal(aqiBand(aqi), band);

// badges
assert.deepEqual(workStatusBadge('planned'), { status: 'pending', label: 'Planned' });
assert.deepEqual(workStatusBadge('moved'), { status: 'warn', label: 'Moved' });
assert.deepEqual(workStatusBadge('shared'), { status: 'approved', label: 'Shared trench' });
assert.deepEqual(workStatusBadge('digging'), { status: 'live', label: 'Digging' });
assert.deepEqual(workStatusBadge('done'), { status: 'ok', label: 'Done' });
assert.deepEqual(workStatusBadge('verified'), { status: 'ok', label: 'Verified' });
assert.deepEqual(workStatusBadge('held'), { status: 'fail', label: 'Money held' });
assert.deepEqual(workStatusBadge('emergency'), { status: 'emergency', label: 'Emergency' });

// metrics
assert.deepEqual(metricDelta(1.6, 3.4, 'digs_per_road'), { delta: '\u221253%', better: true });
assert.deepEqual(metricDelta(0, 7, 'clashes'), { delta: '\u2212100%', better: true });
assert.deepEqual(metricDelta(412, 1096, 'lane_closure_hours'), { delta: '\u221262%', better: true });
assert.deepEqual(metricDelta(0.4, 0, 'days_late'), { delta: '+0.4', better: false });
assert.deepEqual(metricDelta(0, 0, 'trench_hours_in_rain'), { better: true });
assert.equal(compareLabel(3.4), 'Old way 3.4');
assert.equal(compareLabel(1096), 'Old way 1,096');

// errors in plain words
assert.equal(errorText({ status: 0, detail: 'network' }), 'Could not reach MargaMitra. Check that the server is running.');
assert.equal(errorText({ status: 404, detail: 'Not Found' }), 'This is not available yet.');
assert.equal(errorText({ status: 404, detail: 'Unknown work W-999' }), 'Unknown work W-999');
assert.equal(errorText({ status: 409, detail: 'This approval is already decided' }), 'This approval is already decided');
assert.equal(errorText({ status: 422, detail: [{ loc: ['body'], msg: 'field required' }] }), 'Some details are not valid.');
assert.equal(errorText({ status: 422, detail: 'Give a reason to reject' }), 'Give a reason to reject');
assert.equal(errorText({ status: 500, detail: 'Internal Server Error' }), 'Something went wrong on the server. Try again.');
assert.equal(errorText({ status: 503, detail: [] }), 'Something went wrong on the server. Try again.');
assert.equal(errorText({ status: 400, detail: '{"x": 1}' }), 'Something went wrong. Try again.');
assert.equal(errorText({ status: 400, detail: '[1, 2]' }), 'Something went wrong. Try again.');
assert.equal(errorText({ status: 418, detail: 'x'.repeat(200) }).length, 160);
assert.equal(errorText(new Error('boom')), 'Something went wrong. Try again.');
assert.equal(errorText(null), 'Something went wrong. Try again.');
assert.equal(errorText(undefined), 'Something went wrong. Try again.');

// who a message is for
const recipients: [string, string][] = [
  ['water', 'Water'], ['coordinator', 'Coordinator'], ['solver', 'Scheduler'], ['everyone', 'Everyone'],
  ['Scheduler', 'Scheduler'], ['Everyone', 'Everyone'], ['Water', 'Water'],
];
for (const [id, name] of recipients) assert.equal(recipientLabel(id), name);

console.log('format ok');