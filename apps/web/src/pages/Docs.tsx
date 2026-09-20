const metrics = [
  [
    "Count, valid, missing, invalid",
    "Count is the number of rows. Valid values are finite numbers. Empty cells are missing; non-numbers and infinity are invalid.",
  ],
  [
    "Completeness",
    "The share of rows with a valid number: valid ÷ count. For example, 95 valid readings out of 100 means 95% completeness.",
  ],
  [
    "Mean and median",
    "Mean is the usual average. Median is the middle value after sorting; a few extreme values affect it less.",
  ],
  [
    "Standard deviation (std)",
    "How spread out readings are around their mean. A larger value means more variation. Datalight uses the population standard deviation.",
  ],
  [
    "Minimum and maximum",
    "The smallest and largest observed values. They describe this file window; they are not safe operating limits.",
  ],
  [
    "5th and 95th percentiles (q05, q95)",
    "About 5% of readings fall below q05 and 95% below q95. The interval describes the middle 90% of readings.",
  ],
  [
    "Median absolute deviation (MAD)",
    "Find each value’s distance from the median, then take the median of those distances. This measures typical spread without letting a few extreme values dominate.",
  ],
  [
    "Difference standard deviation",
    "The spread of changes from one valid reading to the next within a sequence. It helps describe how jumpy the channel is.",
  ],
  [
    "Lag-1 correlation",
    "How strongly a value follows its immediately preceding value. Near +1 means neighboring readings tend to move together; unavailable means there are too few usable pairs or no variation.",
  ],
  [
    "Median and maximum hold length",
    "How many consecutive samples repeat exactly the same number: the typical hold and the longest hold. Missing values and sequence boundaries end a hold.",
  ],
  [
    "Usable profile",
    "At least 32 valid readings, at most 5% missing or invalid readings, and no rows with the wrong field count in this window. This is a profile quality indicator, not proof of healthy operation.",
  ],
  [
    "Pairwise correlation (r) and count (n)",
    "r compares two channels at matching rows: +1 means they move together, −1 means they move oppositely, and 0 means little linear relationship. n counts pairs with two valid readings. Fewer than three pairs or a constant channel makes r unavailable. Correlation does not prove cause.",
  ],
  [
    "Prediction MAE and forecast count",
    "Mean absolute error averages the distance between a forecast and the value that later arrives. Lower is better in that channel’s own units. The count is the number of valid forecast/target pairs across horizons 1 through 5, not the number of rows.",
  ],
  [
    "Mean slope and slope variability",
    "Slope is the fitted rise or fall per sample over a 10-sample window. Mean slope is its average signed direction; variability is the standard deviation of these slopes. Playback seconds are not real sampling time.",
  ],
  [
    "Reference median, scale and count",
    "The initial window supplies the rule’s reference center and spread. Scale is the largest of 1.4826 × MAD, standard deviation, and a small numerical tolerance. Count is how many valid reference measurements were available; fewer than three makes that rule unavailable.",
  ],
  [
    "Score and threshold",
    "Score = absolute distance from the reference median ÷ reference scale. A score of 7 means seven reference scales away. Automatic process rules require a score strictly greater than 6, with the extra persistence requirement for drift.",
  ],
  [
    "Coverage",
    "Assessed ÷ total monitored channels. A channel is assessed when its reference rules exist and it has a valid 50-sample assessment in this batch. Low coverage means there was not enough usable data to make a full assessment.",
  ],
];

const rules = [
  [
    "Abrupt change",
    "Compare the mean of the latest 10 samples with the mean of the preceding 10. Flag when this difference is more than 6 reference scales away from the initial differences.",
  ],
  [
    "Level deviation",
    "Compare the median of the latest 10 samples with the initial value distribution. Flag when it is more than 6 reference scales away from the initial median.",
  ],
  [
    "Persistent drift",
    "Fit a slope to the latest 50 samples. Check every 10 samples within a continuous sequence. Three consecutive checks must be more than 6 reference scales away in the same direction.",
  ],
  [
    "Missing or invalid values",
    "Any missing numeric cell or non-finite/unparseable numeric value creates a quality warning. Invalid values break affected temporal windows.",
  ],
  [
    "Schema problems",
    "A record with a different number of fields from the header creates a quality warning and cannot supply a valid temporal observation.",
  ],
  [
    "Sequence gaps, duplicates or order",
    "For legacy mounted files with an ordering sample column: skipped coordinates, repeated coordinates, invalid coordinates and backward steps are warnings. A reset to sample 1 starts a new independent sequence. Temporal windows never cross these breaks.",
  ],
  [
    "Configured range",
    "A value strictly below a configured minimum or strictly above a configured maximum creates a quality warning. The bounds themselves are allowed. Outside values are excluded from temporal model inputs. With no configured bounds, this check is unavailable.",
  ],
  [
    "Frozen / stuck value",
    "Warn when an exact-value hold reaches max(20, ceil(5 × median initial completed hold length)) samples. If there were no completed holds, use 20. If the initial channel is constant, the check is inconclusive instead of calling it stuck.",
  ],
  [
    "Custom rule",
    "A confirmed simple threshold rule checks the selected channel. Its chosen effect is either Fault Suspected or a separate quality warning. The rule and its matching observations are recorded as evidence; adding a rule does not change the original reference.",
  ],
];

export default function Docs() {
  return (
    <>
      <div className="page-heading">
        <div>
          <span className="eyebrow">04 / REFERENCE</span>
          <h1>Docs</h1>
          <p>A plain-language guide to the numbers, decisions and evidence.</p>
        </div>
      </div>
      <nav className="docs-links" aria-label="Documentation sections">
        <a href="#reading-data">How analysis works</a>
        <a href="#metrics">Metrics</a>
        <a href="#prediction">Linear regression</a>
        <a href="#faults">Faults & quality</a>
        <a href="#evidence">Evidence</a>
        <a href="#privacy">Privacy & conversation</a>
      </nav>
      <section className="panel docs-section" id="reading-data">
        <h2>Understand first. Monitor next.</h2>
        <p>
          Think of the initial window as a first sketch of what your data
          usually looks like. Datalight computes channel profiles, relationships
          and a fixed reference, then pauses. You choose which numeric channels
          to monitor and can add simple rules before starting playback.
        </p>
        <p>
          Each following batch produces one recorded decision. Batch size
          controls how much data arrives on screen; the automatic rules still
          use sample windows of 10, 20 or 50 readings. The chart initially shows
          the current batch and up to two earlier batches. Scroll its history
          bar to inspect older data and choose Latest to follow playback again.
        </p>
        <p>
          CSV uploads and prepared files use the same analysis. Numeric channels
          are inferred from the initial window; text columns are retained in the
          schema but are not numeric detector inputs. A file needs usable
          numeric observations to support monitoring. Recognized evaluation
          fields and sample are excluded from detector inputs. Uploads use file
          row order; mounted demo files use sample coordinates to detect
          independent sequences. Datalight does not guess physical units or what
          a sensor controls from its name.
        </p>
        <p>
          The initial window is provisional: it may already contain unusual
          behavior. Its observed minimum and maximum are not safety limits, and
          a detected change is not a diagnosis.
        </p>
      </section>
      <section className="panel docs-section" id="metrics">
        <h2>What the metrics mean</h2>
        <p>
          Some metrics appear in the main report; the rest are available in the
          evidence drawer. A missing value means the metric could not be
          computed, not that it equals zero.
        </p>
        <div className="table-scroll docs-table">
          <table>
            <thead>
              <tr>
                <th>Metric</th>
                <th>Simple explanation</th>
              </tr>
            </thead>
            <tbody>
              {metrics.map(([name, meaning]) => (
                <tr key={name}>
                  <th scope="row">{name}</th>
                  <td>{meaning}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
        <p>
          The numerical tolerance used for reference scales is max(10⁻¹², 10⁻⁹ ×
          the largest absolute valid initial value). It avoids dividing by zero
          for nearly constant data.
        </p>
      </section>
      <section className="panel docs-section" id="prediction">
        <h2>Linear regression: a ruler through recent readings</h2>
        <p>
          Imagine drawing the straight line that best follows the last 10 dots
          on a graph. Ordinary least squares (OLS) chooses the line with the
          smallest total squared vertical distance from those dots. Its slope
          says how quickly the readings rise or fall; its intercept sets the
          line’s height.
        </p>
        <p>
          With sample positions 0 through 9, the average position is 4.5. The
          fitted slope is Σ((position − 4.5) × value) ÷ 82.5. A forecast h
          samples ahead is the window mean + slope × (4.5 + h), for h = 1
          through 5.
        </p>
        <p>
          For example, if readings rise by about 2 units per sample, the fitted
          line carries that trend forward. Once the future reading arrives,
          Datalight records the absolute forecast error. The MAE averages these
          errors across all five horizons. The dashed chart line shows only the
          five-step-ahead forecast, aligned to the sample being predicted.
        </p>
        <p>
          The model sees only earlier observations. Missing, invalid,
          out-of-range or discontinuous observations break its windows. A large
          forecast error can be useful evidence, but prediction MAE alone does
          not trigger the built-in process alarm.
        </p>
      </section>
      <section className="panel docs-section" id="faults">
        <h2>Fault categories and their exact criteria</h2>
        <p>
          <strong>Fault Suspected</strong> means at least one automatic
          process-change rule or confirmed custom fault rule fired.{" "}
          <strong>OK</strong> means none fired; limited coverage is shown
          separately. Data-quality warnings stay separate from process status.
          These categories describe observed behavior, not named physical
          failures.
        </p>
        <div className="table-scroll docs-table">
          <table>
            <thead>
              <tr>
                <th>Category</th>
                <th>Criterion</th>
              </tr>
            </thead>
            <tbody>
              {rules.map(([name, criterion]) => (
                <tr key={name}>
                  <th scope="row">{name}</th>
                  <td>{criterion}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
        <h3>Adding a simple rule</h3>
        <p>
          Before first Play, describe one channel and a condition, such as “flag
          a fault if pressure exceeds 50”. Supported conditions are greater
          than, at least, less than, at most, outside a range, or missing.
          Outside a range means below its minimum or above its maximum; values
          equal to either bound are inside. Missing means an empty cell, not
          every invalid value.
        </p>
        <p>
          Review the proposed channel, condition and effect, then choose Apply.
          A proposal has no effect until you apply it. Compound conditions,
          formulas and duration rules require clarification. First Play locks
          the monitoring setup; start a new analysis to use different channels
          or rules.
        </p>
        <p>
          Every built-in process rule uses the fixed initial reference. Custom
          rules use their explicitly applied thresholds. Abrupt-change
          references use initial differences between adjacent 10-sample means;
          drift references use initial 50-sample slopes; level references use
          initial valid readings. Consecutive alarms are grouped into intervals,
          with the strongest score retained.
        </p>
        <p>
          Units and real-time delivery checks are unavailable when the file
          supplies no established units or delivery schedule. A pass says a
          configured check found no violation. Unavailable says the evidence or
          configuration needed to judge it is missing.
        </p>
      </section>
      <section className="panel docs-section" id="evidence">
        <h2>How to read an evidence snippet</h2>
        <p>
          Evidence is the recorded calculation behind a claim. Numbered links
          open individual records; their numbers are local to that answer or
          explanation. The persistent evidence ID is the stable reference.
        </p>
        <dl className="docs-definitions">
          <dt>Identity and location</dt>
          <dd>
            Each record belongs to an analysis and a batch. IDs commonly look
            like analysis-id:b3:temporal:c001: batch 3, temporal evidence,
            channel c001. Batch 0 is the initial report. Channel IDs are local
            labels, not sensor types.
          </dd>
          <dt>Profile</dt>
          <dd>
            Counts, distribution and continuity metrics for one channel and
            window, including whether the profile was usable.
          </dd>
          <dt>Temporal</dt>
          <dd>
            The fixed reference, current forecast errors and triggered
            intervals. reference_evidence_id links back to the original
            reference record.
          </dd>
          <dt>Correlation</dt>
          <dd>
            The two channel IDs, paired count, correlation coefficient and an
            explanation when it is unavailable.
          </dd>
          <dt>Quality</dt>
          <dd>
            The check name, pass/fail/unavailable status, affected count and
            explanation. Different checks count different things: a frozen
            check, for example, records whether a warning occurred.
          </dd>
          <dt>Decision and custom rules</dt>
          <dd>
            The automatic status, coverage, warning list, forecast errors and
            rule matches. A custom-rule match identifies the rule, channel,
            effect, violation count and affected row range.
          </dd>
          <dt>Trigger fields</dt>
          <dd>
            value is the measured feature; reference is the initial median;
            scale is its reference spread; score is the distance in scales;
            threshold is the required score. row_start and row_end describe the
            affected interval. detected_at records the first detection
            coordinate for a grouped interval.
          </dd>
        </dl>
        <h3>A small synthetic example</h3>
        <pre>
          {JSON.stringify(
            {
              id: "example-analysis:b3:temporal:c001",
              run_id: "example-analysis",
              batch_index: 3,
              kind: "temporal",
              details: {
                reference_evidence_id: "example-analysis:b0:temporal:c001",
                triggers: [
                  {
                    channel_id: "c001",
                    kind: "level",
                    value: 24,
                    reference: 10,
                    scale: 2,
                    score: 7,
                    threshold: 6,
                    row_start: 301,
                    row_end: 310,
                    detected_at: 310,
                  },
                ],
              },
            },
            null,
            2,
          )}
        </pre>
        <p>
          This invented example says that the recent median, 24, is seven
          reference scales above the initial median, 10. Seven exceeds the
          threshold of six, so the level rule flagged this interval. Follow
          reference_evidence_id to see how the original reference was
          calculated.
        </p>
        <p>
          Sample rows locate observations in the CSV replay. They are not
          timestamps. The local database preserves evidence, decisions, model
          attempts, questions, answers and review history; raw observations
          remain in the local CSV.
        </p>
        <p>
          Accept and override append a human assessment. An override requires a
          reason and changes the displayed human assessment; it never rewrites
          the original decision or its evidence. Accept returns the human
          assessment to the automated result. Questions do not change decisions,
          rules or reference values.
        </p>
      </section>
      <section className="panel docs-section" id="privacy">
        <h2>Private data, evidence-grounded conversation</h2>
        <p>
          CSV files and raw observations stay on this deployment’s local
          storage. When a model is configured, it receives computed summaries
          and your explicit questions, with channel names replaced by opaque
          IDs. Raw rows, observation sequences and evaluation metadata are not
          attached. Do not paste raw readings or secrets into a question.
        </p>
        <p>
          Keep asking follow-up questions on the same decision. The next answer
          uses its evidence plus up to the latest 10 completed
          question-and-answer turns for that decision. Older turns remain in the
          local review history even when they fall outside the model’s context.
          Only one question is processed at a time per decision. Rule proposals
          send only the sanitized request and eligible opaque channel IDs; no
          observations or profile statistics are needed.
        </p>
        <p>
          Model explanations are interpretations, not verified diagnoses. Their
          evidence links must reference stored records, but a valid citation
          does not prove the interpretation is correct. If the provider is
          unavailable, deterministic monitoring and local evidence still work.
        </p>
      </section>
    </>
  );
}
