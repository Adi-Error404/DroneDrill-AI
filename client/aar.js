// DroneDrill AI - After Action Review (AAR) Logic & SVG Timeline
// SIH 2026, PS 26247, Team NexxGenX

(function () {
  'use strict';

  const apiBase = (window.CONFIG && window.CONFIG.API_BASE) || 'http://127.0.0.1:8000';
  const traineeId = (window.CONFIG && window.CONFIG.TRAINEE_ID) || 'demo_trainee_01';

  let currentSessionId = null;

  window.addEventListener('DOMContentLoaded', async () => {
    // Check URL query parameters: ?session=SESSION_ID
    const urlParams = new URLSearchParams(window.location.search);
    const querySessionId = urlParams.get('session');

    setupPrintButton();
    await initSessionPicker(querySessionId);
  });

  function setupPrintButton() {
    const btn = document.getElementById('btn-print-aar');
    if (btn) {
      btn.addEventListener('click', () => window.print());
    }
  }

  async function initSessionPicker(preferredSessionId) {
    const select = document.getElementById('session-select');
    try {
      const res = await fetch(`${apiBase}/trainee/${traineeId}/performance`);
      if (!res.ok) throw new Error(await res.text());
      const data = await res.json();
      const sessions = data.sessions || [];

      if (sessions.length === 0) {
        select.innerHTML = '<option value="">No completed sessions found</option>';
        return;
      }

      select.innerHTML = '';
      // Reverse to show most recent first
      const revSessions = [...sessions].reverse();

      revSessions.forEach((s, idx) => {
        const opt = document.createElement('option');
        opt.value = s.session_id;
        const scorePct = s.overall !== null ? `${Math.round(s.overall * 100)}%` : '--';
        opt.textContent = `Session ${sessions.length - idx} (${s.mode || 'practice'}) - Score: ${scorePct} [${s.session_id.substring(0, 8)}]`;
        select.appendChild(opt);
      });

      // Select preferred or first
      if (preferredSessionId && sessions.some(s => s.session_id === preferredSessionId)) {
        select.value = preferredSessionId;
      } else {
        select.value = revSessions[0].session_id;
      }

      currentSessionId = select.value;
      select.addEventListener('change', (e) => {
        currentSessionId = e.target.value;
        loadAARData(currentSessionId);
      });

      if (currentSessionId) {
        await loadAARData(currentSessionId);
      }
    } catch (e) {
      console.error('Failed to load session history:', e);
      document.getElementById('api-banner').classList.add('active');
    }
  }

  async function loadAARData(sessionId) {
    if (!sessionId) return;

    try {
      const res = await fetch(`${apiBase}/aar/${sessionId}`);
      if (!res.ok) throw new Error(await res.text());
      const aar = await res.json();

      renderAAROverview(aar);
      renderTimelineSVG(aar);
      renderErrorTaxonomy(aar);
    } catch (e) {
      console.error('Failed to load AAR data:', e);
      alert(`Error loading AAR data: ${e.message}`);
    }
  }

  function renderAAROverview(aar) {
    const scoreVal = aar.overall_score !== null && aar.overall_score !== undefined
      ? `${Math.round(aar.overall_score * 100)}%`
      : '--%';
    document.getElementById('aar-overall-score').textContent = scoreVal;
    document.getElementById('aar-trainee-id').textContent = aar.trainee_id || traineeId;

    // Feedback Sentences
    const listEl = document.getElementById('aar-feedback-list');
    listEl.innerHTML = '';
    const sentences = aar.feedback_sentences || [];
    if (sentences.length === 0) {
      listEl.innerHTML = '<li>Exemplary execution: All targets identified and engaged without procedural errors.</li>';
    } else {
      sentences.forEach(s => {
        const li = document.createElement('li');
        li.textContent = s;
        listEl.appendChild(li);
      });
    }

    // Confidence Calibration Note
    const calEl = document.getElementById('aar-calibration-note');
    calEl.innerHTML = `<strong>Confidence Calibration:</strong> ${aar.confidence_vs_correctness || 'Normal alignment between assessment certainty and accuracy.'}`;
  }

  // --- SVG Multi-Lane Timeline Renderer ---
  function renderTimelineSVG(aar) {
    const svg = document.getElementById('timeline-svg');
    svg.innerHTML = '';

    const timeline = aar.timeline || [];
    if (timeline.length === 0) return;

    // Determine max simulation time
    let maxT = 60.0;
    timeline.forEach(item => {
      const appT = item.ground_truth?.appears_at_time || 0;
      const detT = item.trainee_action?.detect_time_s || 0;
      maxT = Math.max(maxT, appT + 10, detT + 5);
      (item.sensor_visibility || []).forEach(w => {
        maxT = Math.max(maxT, w.to_t);
      });
    });

    const svgW = 1000;
    const padL = 140;
    const padR = 40;
    const trackW = svgW - padL - padR;

    const rowH = 75;
    const totalH = Math.max(280, 50 + timeline.length * rowH);
    svg.setAttribute('viewBox', `0 0 ${svgW} ${totalH}`);

    // Helper: Map time t (seconds) to X coordinate
    const timeToX = (t) => padL + (Math.max(0, Math.min(maxT, t)) / maxT) * trackW;

    // Time Axis Ticks & Lines
    const stepT = maxT > 90 ? 15 : 10;
    for (let t = 0; t <= maxT; t += stepT) {
      const x = timeToX(t);

      const line = document.createElementNS('http://www.w3.org/2000/svg', 'line');
      line.setAttribute('x1', x);
      line.setAttribute('y1', 25);
      line.setAttribute('x2', x);
      line.setAttribute('y2', totalH - 30);
      line.setAttribute('stroke', 'rgba(255, 255, 255, 0.05)');
      line.setAttribute('stroke-dasharray', '2,4');
      svg.appendChild(line);

      const label = document.createElementNS('http://www.w3.org/2000/svg', 'text');
      label.setAttribute('x', x);
      label.setAttribute('y', totalH - 12);
      label.setAttribute('class', 'axis-label');
      label.textContent = `${t}s`;
      svg.appendChild(label);
    }

    // Lane Headers Legend
    const lanesLegend = [
      { name: 'Ground Truth', y: 15, color: '#e11d2e' },
      { name: 'Sensor Visibility', y: 15, color: '#22c55e' },
      { name: 'Trainee Action', y: 15, color: '#eab308' },
    ];

    // Render Each Target Object's Multi-Lane Track
    timeline.forEach((item, idx) => {
      const baseY = 40 + idx * rowH;
      const gt = item.ground_truth || {};
      const act = item.trainee_action || {};
      const vis = item.sensor_visibility || [];

      // Row separator line
      const rowSep = document.createElementNS('http://www.w3.org/2000/svg', 'line');
      rowSep.setAttribute('x1', padL - 100);
      rowSep.setAttribute('y1', baseY + rowH - 10);
      rowSep.setAttribute('x2', svgW - padR);
      rowSep.setAttribute('y2', baseY + rowH - 10);
      rowSep.setAttribute('stroke', 'rgba(255, 255, 255, 0.08)');
      svg.appendChild(rowSep);

      // Target Label
      const objTitle = document.createElementNS('http://www.w3.org/2000/svg', 'text');
      objTitle.setAttribute('x', padL - 15);
      objTitle.setAttribute('y', baseY + 24);
      objTitle.setAttribute('class', 'lane-title');
      objTitle.textContent = `${gt.object_id || `Contact ${idx + 1}`}`;
      svg.appendChild(objTitle);

      const objSub = document.createElementNS('http://www.w3.org/2000/svg', 'text');
      objSub.setAttribute('x', padL - 15);
      objSub.setAttribute('y', baseY + 42);
      objSub.setAttribute('class', 'lane-title');
      objSub.setAttribute('fill', 'var(--text-muted)');
      objSub.setAttribute('font-size', '9px');
      objSub.textContent = `Thr ${gt.true_threat_level} | ${gt.expected_response}`;
      svg.appendChild(objSub);

      // 1. Lane 1: Ground Truth Appearance
      const appearX = timeToX(gt.appears_at_time || 0);
      const gtCircle = document.createElementNS('http://www.w3.org/2000/svg', 'circle');
      gtCircle.setAttribute('cx', appearX);
      gtCircle.setAttribute('cy', baseY + 12);
      gtCircle.setAttribute('r', 5);
      gtCircle.setAttribute('fill', '#e11d2e');
      svg.appendChild(gtCircle);

      const gtText = document.createElementNS('http://www.w3.org/2000/svg', 'text');
      gtText.setAttribute('x', appearX + 8);
      gtText.setAttribute('y', baseY + 15);
      gtText.setAttribute('font-size', '10px');
      gtText.setAttribute('fill', '#ececf0');
      gtText.setAttribute('font-family', 'var(--font-mono)');
      gtText.textContent = `${gt.true_class} (entered @ ${gt.appears_at_time}s)`;
      svg.appendChild(gtText);

      // 2. Lane 2: Sensor Visibility Windows
      const visY = baseY + 28;
      vis.forEach(w => {
        const x1 = timeToX(w.from_t);
        const x2 = timeToX(w.to_t);
        const wWidth = Math.max(2, x2 - x1);

        const rect = document.createElementNS('http://www.w3.org/2000/svg', 'rect');
        rect.setAttribute('x', x1);
        rect.setAttribute('y', visY);
        rect.setAttribute('width', wWidth);
        rect.setAttribute('height', 10);
        rect.setAttribute('rx', 2);

        if (w.visible) {
          rect.setAttribute('fill', 'rgba(34, 197, 94, 0.4)');
          rect.setAttribute('stroke', '#22c55e');
        } else {
          rect.setAttribute('fill', 'rgba(220, 38, 38, 0.3)');
          rect.setAttribute('stroke', '#e11d2e');
          rect.setAttribute('stroke-dasharray', '2,2');
        }

        const titleTag = document.createElementNS('http://www.w3.org/2000/svg', 'title');
        titleTag.textContent = `${w.from_t}s - ${w.to_t}s: ${w.reason}`;
        rect.appendChild(titleTag);

        svg.appendChild(rect);
      });

      // 3. Lane 3: Trainee Action Marker
      const actY = baseY + 50;
      if (act.detected && act.detect_time_s !== null) {
        const detX = timeToX(act.detect_time_s);

        // Marker diamond / triangle
        const marker = document.createElementNS('http://www.w3.org/2000/svg', 'polygon');
        marker.setAttribute('points', `${detX},${actY - 5} ${detX + 5},${actY + 3} ${detX - 5},${actY + 3}`);
        marker.setAttribute('fill', '#eab308');
        svg.appendChild(marker);

        const isCorrectCls = (act.classified_as === gt.true_class);
        const clsColor = isCorrectCls ? '#22c55e' : '#e11d2e';

        const actText = document.createElementNS('http://www.w3.org/2000/svg', 'text');
        actText.setAttribute('x', detX + 8);
        actText.setAttribute('y', actY + 3);
        actText.setAttribute('font-size', '10px');
        actText.setAttribute('fill', clsColor);
        actText.setAttribute('font-family', 'var(--font-mono)');
        actText.textContent = `Det @ ${act.detect_time_s}s: ${act.classified_as} (Thr ${act.threat_level_rated}, ${act.response_chosen}, Conf ${(act.confidence * 100).toFixed(0)}%)`;
        svg.appendChild(actText);
      } else {
        // Target Missed
        const missText = document.createElementNS('http://www.w3.org/2000/svg', 'text');
        missText.setAttribute('x', appearX + 8);
        missText.setAttribute('y', actY + 2);
        missText.setAttribute('font-size', '10px');
        missText.setAttribute('fill', '#e11d2e');
        missText.setAttribute('font-weight', '700');
        missText.textContent = '✕ TARGET MISSED';
        svg.appendChild(missText);
      }
    });
  }

  // --- Error Taxonomy Breakdown ---
  function renderErrorTaxonomy(aar) {
    const list = document.getElementById('aar-error-list');
    list.innerHTML = '';

    const errors = aar.errors || {};
    let errorCount = 0;

    // 1. Missed Targets
    (errors.missed || []).forEach(oid => {
      errorCount++;
      const item = document.createElement('div');
      item.className = 'error-item';
      item.innerHTML = `
        <span class="error-tag">Missed Target</span>
        <span>Target <strong>${oid}</strong> was never detected during its sensor visibility window.</span>
      `;
      list.appendChild(item);
    });

    // 2. Misclassifications (with confusion pair)
    (errors.misclassifications || []).forEach(m => {
      errorCount++;
      const item = document.createElement('div');
      item.className = 'error-item';
      item.innerHTML = `
        <span class="error-tag">Misclassification</span>
        <span>Target <strong>${m.object_id}</strong> (${m.true_class}) misclassified as <strong>${m.classified_as}</strong> (Confusion Pair: <em>${m.confusion_pair}</em>).</span>
      `;
      list.appendChild(item);
    });

    // 3. Wrong Threat Levels
    (errors.wrong_threat_levels || []).forEach(wt => {
      errorCount++;
      const item = document.createElement('div');
      item.className = 'error-item warning';
      item.innerHTML = `
        <span class="error-tag">Threat Level Variance</span>
        <span>Target <strong>${wt.object_id}</strong> rated Priority ${wt.rated_level} (Expected: Priority ${wt.expected_level}).</span>
      `;
      list.appendChild(item);
    });

    // 4. Suboptimal Decision Tree Responses
    (errors.suboptimal_responses || []).forEach(sr => {
      errorCount++;
      const item = document.createElement('div');
      item.className = 'error-item warning';
      item.innerHTML = `
        <span class="error-tag">Response Discrepancy</span>
        <span>Target <strong>${sr.object_id}</strong> received response choice '<em>${sr.chosen_response}</em>' (Optimal Protocol: '<em>${sr.expected_response}</em>').</span>
      `;
      list.appendChild(item);
    });

    // 5. False Alarms
    if (errors.false_alarms > 0) {
      errorCount++;
      const item = document.createElement('div');
      item.className = 'error-item warning';
      item.innerHTML = `
        <span class="error-tag">False Alarm</span>
        <span><strong>${errors.false_alarms}</strong> non-target clicks logged in clear airspace.</span>
      `;
      list.appendChild(item);
    }

    if (errorCount === 0) {
      list.innerHTML = '<div style="font-size: 13px; color: var(--accent-green); padding: 10px 14px; background: rgba(0,230,118,0.1); border-radius: 6px; font-weight: 600;">Perfect score: Zero missed targets, classification errors, or procedural response variances.</div>';
    }
  }

})();
