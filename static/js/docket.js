(() => {
  'use strict';

  const state = {
    page: 1,
    perPage: 10,
    pages: 1,
    search: '',
    type: 'all',
    status: 'all',
    searchTimer: null,
  };

  const $ = (selector) => document.querySelector(selector);
  const escapeHtml = (value) => String(value ?? '').replace(/[&<>'"]/g, (character) => ({
    '&': '&amp;', '<': '&lt;', '>': '&gt;', "'": '&#39;', '"': '&quot;'
  })[character]);
  const label = (value) => String(value || '—').replace(/_/g, ' ').replace(/\b\w/g, (letter) => letter.toUpperCase());
  const formatDate = (value, withTime = false) => {
    if (!value) return '—';
    const date = new Date(value);
    if (Number.isNaN(date.getTime())) return escapeHtml(value);
    return new Intl.DateTimeFormat(undefined, withTime ? {
      dateStyle: 'medium', timeStyle: 'short'
    } : { dateStyle: 'medium' }).format(date);
  };
  const badgeClass = (value) => {
    const normalized = String(value || '').toLowerCase();
    if (['granted', 'registered', 'allowed', 'completed'].includes(normalized)) return 'docket-badge-success';
    if (['overdue', 'abandoned', 'rejected'].includes(normalized)) return 'docket-badge-danger';
    if (['pending', 'examination', 'appeal', 'opposition', 'extended'].includes(normalized)) return 'docket-badge-warning';
    if (['patent', 'trademark', 'design_patent', 'pct_application'].includes(normalized)) return 'docket-badge-primary';
    return 'docket-badge-muted';
  };
  const typeIcon = (value) => value === 'trademark' ? 'bi-badge-tm' : 'bi-file-earmark-text';

  async function fetchJson(url, options = {}) {
    const response = await fetch(url, { credentials: 'same-origin', ...options });
    const contentType = response.headers.get('content-type') || '';
    const payload = contentType.includes('application/json') ? await response.json() : {};
    if (!response.ok) throw new Error(payload.error || payload.message || `Request failed (${response.status})`);
    return payload;
  }

  function setText(selector, value) {
    const element = $(selector);
    if (element) element.textContent = value;
  }

  function renderDashboard(payload) {
    const stats = payload.statistics || {};
    setText('#totalCases', stats.total_cases ?? 0);
    setText('#activeCases', stats.active_cases ?? 0);
    setText('#overdueDeadlines', stats.overdue_deadlines ?? 0);
    setText('#upcomingDeadlines', stats.upcoming_deadlines ?? 0);

    const today = new Intl.DateTimeFormat(undefined, { dateStyle: 'full' }).format(new Date());
    setText('#todayLabel', today);

    const deadlines = payload.deadlines || [];
    const deadlinesList = $('#deadlinesList');
    if (deadlinesList) {
      deadlinesList.innerHTML = deadlines.length ? deadlines.map((deadline) => {
        const overdue = deadline.status === 'overdue' || new Date(deadline.due_date) < new Date();
        return `<div class="docket-deadline-item ${overdue ? 'is-overdue' : ''}">
          <div class="docket-deadline-icon"><i class="bi ${overdue ? 'bi-exclamation-triangle' : 'bi-calendar-event'}"></i></div>
          <div class="docket-deadline-copy">
            <strong>${escapeHtml(deadline.title || label(deadline.deadline_type))}</strong>
            <span>${escapeHtml(deadline.case_number || deadline.case_title || 'Case')} · ${escapeHtml(label(deadline.status))}</span>
          </div>
          <div class="docket-deadline-date">${formatDate(deadline.due_date)}</div>
        </div>`;
      }).join('') : '<div class="docket-empty"><i class="bi bi-calendar2-check"></i><strong>No upcoming actions</strong><span>Your next 30 days are clear.</span></div>';
    }

    const activity = payload.activity || [];
    const activityList = $('#activityList');
    if (activityList) {
      activityList.innerHTML = activity.length ? activity.map((event) => `<div class="docket-activity-item">
        <div class="docket-activity-icon"><i class="bi bi-arrow-repeat"></i></div>
        <div class="docket-activity-copy">
          <strong>${escapeHtml(event.case_title || 'Case update')}</strong>
          <span>${escapeHtml(label(event.old_status))} → ${escapeHtml(label(event.new_status))}</span>
          <span>${formatDate(event.change_date, true)}</span>
        </div>
      </div>`).join('') : '<div class="docket-empty"><i class="bi bi-clock-history"></i><strong>No activity yet</strong><span>Status changes will appear here.</span></div>';
    }

    const automation = payload.automation || {};
    const ready = automation.pending_uploads === 0;
    setText('#automationLabel', automation.last_upload_status ? `${label(automation.last_upload_status)} · ${automation.pending_uploads || 0} pending` : 'Ready for uploads');
    $('#automationDot')?.classList.toggle('is-idle', !ready);
  }

  function renderCases(payload) {
    const body = $('#casesTableBody');
    if (!body) return;
    const cases = payload.cases || [];
    state.pages = payload.pagination?.pages || 1;
    state.page = payload.pagination?.page || 1;

    if (!cases.length) {
      body.innerHTML = '<tr><td colspan="6"><div class="docket-empty"><i class="bi bi-search"></i><strong>No cases found</strong><span>Try a different search or filter.</span></div></td></tr>';
    } else {
      body.innerHTML = cases.map((caseItem) => `<tr>
        <td>
          <span class="case-number">${escapeHtml(caseItem.case_number)}</span>
          <span class="case-subtitle">${escapeHtml(caseItem.application_number)}</span>
        </td>
        <td><span class="docket-badge ${badgeClass(caseItem.type)}"><i class="bi ${typeIcon(caseItem.type)}"></i>${escapeHtml(label(caseItem.type))}</span></td>
        <td><span class="docket-badge ${badgeClass(caseItem.status)}">${escapeHtml(label(caseItem.status))}</span></td>
        <td>${formatDate(caseItem.filing_date)}</td>
        <td><span class="docket-badge ${caseItem.open_deadline_count ? 'docket-badge-warning' : 'docket-badge-muted'}">${caseItem.open_deadline_count || 0} open</span></td>
        <td><button class="docket-table-action js-case-details" type="button" data-case-id="${Number(caseItem.id)}" aria-label="Open case details"><i class="bi bi-arrow-up-right"></i></button></td>
      </tr>`).join('');
      body.querySelectorAll('.js-case-details').forEach((button) => button.addEventListener('click', () => openCaseDetails(button.dataset.caseId)));
    }

    const total = payload.pagination?.total || 0;
    const start = total ? ((state.page - 1) * state.perPage) + 1 : 0;
    const end = Math.min(state.page * state.perPage, total);
    setText('#casePaginationLabel', total ? `Showing ${start}–${end} of ${total} cases` : 'No cases to display');
    const previous = $('#previousPage');
    const next = $('#nextPage');
    if (previous) previous.disabled = !payload.pagination?.has_prev;
    if (next) next.disabled = !payload.pagination?.has_next;
  }

  async function loadCases() {
    const params = new URLSearchParams({
      page: state.page,
      per_page: state.perPage,
      search: state.search,
      type: state.type,
      status: state.status,
    });
    try {
      const payload = await fetchJson(`/docket/api/cases?${params.toString()}`);
      renderCases(payload);
    } catch (error) {
      const body = $('#casesTableBody');
      if (body) body.innerHTML = `<tr><td colspan="6"><div class="docket-empty"><i class="bi bi-wifi-off"></i><strong>Could not load cases</strong><span>${escapeHtml(error.message)}</span></div></td></tr>`;
      setText('#casePaginationLabel', 'Unable to load cases');
    }
  }

  async function openCaseDetails(caseId) {
    const modalElement = $('#caseDetailsModal');
    const modal = bootstrap.Modal.getOrCreateInstance(modalElement);
    const body = $('#caseDetailsBody');
    if (!modalElement || !body) return;
    $('#caseDetailsTitle').textContent = 'Loading case…';
    $('#caseDetailsNumber').textContent = 'Case details';
    body.innerHTML = '<div class="text-center py-5"><span class="spinner-border text-primary" role="status"></span></div>';
    modal.show();

    try {
      const payload = await fetchJson(`/docket/api/cases/${Number(caseId)}/details`);
      const item = payload.case;
      $('#caseDetailsTitle').textContent = item.title || item.case_number;
      $('#caseDetailsNumber').textContent = `${item.case_number} · ${item.application_number}`;
      body.innerHTML = `<div class="docket-detail-grid">
        <div class="docket-detail-item"><small>Case type</small><strong>${escapeHtml(label(item.type))}</strong></div>
        <div class="docket-detail-item"><small>Status</small><strong><span class="docket-badge ${badgeClass(item.status)}">${escapeHtml(label(item.status))}</span></strong></div>
        <div class="docket-detail-item"><small>Filing date</small><strong>${formatDate(item.filing_date)}</strong></div>
        <div class="docket-detail-item"><small>Fee status</small><strong>${escapeHtml(label(item.fee_status))}</strong></div>
      </div>
      <div class="docket-modal-section"><h3>About this case</h3><p class="text-secondary small mb-0">${escapeHtml(item.description || 'No description has been added.')}</p></div>
      <div class="docket-modal-section"><h3>Deadlines</h3><div class="docket-modal-list">${renderDetailDeadlines(payload.deadlines)}</div></div>
      <div class="docket-modal-section"><h3>Status history</h3><div class="docket-modal-list">${renderHistory(payload.status_history)}</div></div>
      <div class="docket-modal-section"><h3>Office actions</h3><div class="docket-modal-list">${renderOfficeActions(payload.office_actions)}</div></div>`;
    } catch (error) {
      body.innerHTML = `<div class="docket-empty"><i class="bi bi-exclamation-circle"></i><strong>Unable to load this case</strong><span>${escapeHtml(error.message)}</span></div>`;
    }
  }

  function renderDetailDeadlines(items) {
    if (!items?.length) return '<div class="docket-empty py-3"><span>No deadlines recorded.</span></div>';
    return items.map((item) => `<div class="docket-modal-list-item"><div><strong>${escapeHtml(item.title || label(item.deadline_type))}</strong><br><span>${escapeHtml(item.description || label(item.deadline_type))}</span></div><div class="text-end"><span class="docket-badge ${badgeClass(item.status)}">${escapeHtml(label(item.status))}</span><br><span>${formatDate(item.due_date)}</span></div></div>`).join('');
  }
  function renderHistory(items) {
    if (!items?.length) return '<div class="docket-empty py-3"><span>No status history recorded.</span></div>';
    return items.map((item) => `<div class="docket-modal-list-item"><div><strong>${escapeHtml(label(item.new_status))}</strong><br><span>${escapeHtml(item.status_description || item.source || 'Status update')}</span></div><span>${formatDate(item.change_date, true)}</span></div>`).join('');
  }
  function renderOfficeActions(items) {
    if (!items?.length) return '<div class="docket-empty py-3"><span>No office actions recorded.</span></div>';
    return items.map((item) => `<div class="docket-modal-list-item"><div><strong>${escapeHtml(label(item.oa_type))} · ${escapeHtml(item.oa_number)}</strong><br><span>Mailed ${formatDate(item.mailing_date)} · Due ${formatDate(item.due_date)}</span></div><span class="docket-badge ${item.response_filed ? 'docket-badge-success' : 'docket-badge-warning'}">${item.response_filed ? 'Responded' : 'Pending'}</span></div>`).join('');
  }

  function bindEvents() {
    $('#caseTypeFilter')?.addEventListener('change', (event) => { state.type = event.target.value; state.page = 1; loadCases(); });
    $('#caseStatusFilter')?.addEventListener('change', (event) => { state.status = event.target.value; state.page = 1; loadCases(); });
    $('#caseSearch')?.addEventListener('input', (event) => {
      clearTimeout(state.searchTimer);
      state.searchTimer = setTimeout(() => { state.search = event.target.value.trim(); state.page = 1; loadCases(); }, 250);
    });
    $('#previousPage')?.addEventListener('click', () => { if (state.page > 1) { state.page -= 1; loadCases(); } });
    $('#nextPage')?.addEventListener('click', () => { if (state.page < state.pages) { state.page += 1; loadCases(); } });
  }

  async function init() {
    bindEvents();
    try {
      const dashboard = await fetchJson('/docket/api/dashboard');
      renderDashboard(dashboard);
    } catch (error) {
      setText('#automationLabel', `Dashboard unavailable: ${error.message}`);
    }
    await loadCases();
  }

  document.addEventListener('DOMContentLoaded', init);
})();
