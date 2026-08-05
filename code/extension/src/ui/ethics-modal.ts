/**
 * The blocking ethics modal.
 *
 * Spec section 7: "which tool you use is advisory, what you ask it to do is
 * blocking." There is no Ignore here and no rewrite -- a covert-surveillance
 * script is not fixable by masking a name, so the only ways out are editing the
 * prompt or abandoning it.
 */
import { explain } from '../detection/explanations';

const HOST_ATTR = 'data-vanguard-ui';

export type ReviewItem = {
  id?: string;
  category?: string;
  display_name?: string;
  status?: string;
  access_state?: string;
  admin_note?: string | null;
  reason_code?: string | null;
  remediation_guidance?: string | null;
  created_at?: string;
  employee_reason?: string;
  reason?: string;
};

export type EthicsModalOptions = {
  label: string;
  category: string;
  orgName: string;
  promptText?: string;                       // present only so the employee CAN opt in to share it
  reviews?: ReviewItem[];
  fetchReviews?: () => Promise<ReviewItem[]>;
  onEdit: () => void;
  onRequestReview: (reason: string, disclosedText?: string) => void;
};

export function hideEthicsModal(): void {
  document.querySelector(`[${HOST_ATTR}="ethics-modal"]`)?.remove();
}

export function showEthicsModal(options: EthicsModalOptions): void {
  hideEthicsModal();

  const host = document.createElement('div');
  host.setAttribute(HOST_ATTR, 'ethics-modal');
  const root = host.attachShadow({ mode: 'open' });

  const style = document.createElement('style');
  style.textContent = `
    .scrim { position: fixed; inset: 0; z-index: 2147483647; display: grid;
             place-items: center; background: rgb(15 23 42 / 60%); backdrop-filter: blur(4px); padding: 20px; box-sizing: border-box; }
    .modal-container { display: flex; gap: 20px; max-width: 920px; width: 100%; align-items: stretch; justify-content: center; }
    .box { background: #fff; border-radius: 12px; overflow: hidden;
           font: 15px/1.5 system-ui, -apple-system, sans-serif; box-shadow: 0 20px 50px rgb(0 0 0 / 30%); }
    .box.main-card { flex: 1 1 480px; max-width: 500px; display: flex; flex-direction: column; }
    .box.reviews-card { flex: 1 1 340px; max-width: 380px; display: flex; flex-direction: column; background: #fafafa; border: 1px solid #e2e8f0; }
    .head { background: #b91c1c; color: #fff; padding: 16px 20px; font-weight: 600; }
    .reviews-head { background: #f1f5f9; color: #0f172a; padding: 16px 20px; font-weight: 600; border-bottom: 1px solid #e2e8f0; display: flex; justify-content: space-between; align-items: center; }
    .reviews-body { padding: 16px; flex: 1; overflow-y: auto; max-height: 440px; display: flex; flex-direction: column; gap: 12px; }
    .body { padding: 20px; color: #0f172a; flex: 1; }
    .policy { margin: 14px 0; padding: 12px 14px; background: #fef2f2;
              border-left: 3px solid #b91c1c; border-radius: 4px; font-weight: 600; }
    .foot { padding: 0 20px 20px; display: flex; gap: 10px; justify-content: flex-end; align-items: center; }
    button { border: none; border-radius: 6px; padding: 9px 16px; cursor: pointer;
             background: #b91c1c; color: #fff; font-size: 14px; font-weight: 500; }
    .why { margin: 12px 0 0; }
    .note { margin: 8px 0 0; color: #64748b; font-size: 13px; }
    .review { margin-top: 14px; }
    .review label { display: block; font-size: 13px; color: #334155; }
    .review textarea { width: 100%; box-sizing: border-box; margin-top: 6px; padding: 8px;
                       border: 1px solid #cbd5e1; border-radius: 6px; font: inherit; }
    .review .optin { display: flex; gap: 8px; align-items: flex-start; margin-top: 10px; font-size: 13px; color: #334155; }
    button.ghost { background: #fff; color: #b91c1c; border: 1px solid #fecaca; margin-right: auto; }

    .review-item { background: #fff; border: 1px solid #e2e8f0; border-radius: 8px; padding: 12px; font-size: 13px; display: flex; flex-direction: column; gap: 6px; box-shadow: 0 1px 3px rgba(0,0,0,0.05); }
    .review-header { display: flex; justify-content: space-between; align-items: center; gap: 8px; }
    .review-title { font-weight: 600; color: #1e293b; word-break: break-word; }
    .status-badge { padding: 2px 8px; border-radius: 12px; font-size: 11px; font-weight: 600; text-transform: uppercase; letter-spacing: 0.5px; white-space: nowrap; }
    .status-pending, .status-in_review { background: #fffbeb; color: #b45309; border: 1px solid #fde68a; }
    .status-approved, .status-overturned { background: #f0fdf4; color: #15803d; border: 1px solid #bbf7d0; }
    .status-blocked, .status-upheld { background: #fef2f2; color: #b91c1c; border: 1px solid #fecaca; }
    .review-desc { color: #475569; line-height: 1.4; }
    .review-note { background: #f8fafc; border-left: 2px solid #94a3b8; padding: 6px 8px; border-radius: 2px; color: #334155; font-size: 12px; margin-top: 2px; }
    .empty-reviews { color: #64748b; font-size: 13px; text-align: center; padding: 30px 10px; }
  `;

  const scrim = document.createElement('div');
  scrim.className = 'scrim';
  scrim.innerHTML = `
    <div class="modal-container">
      <div class="box main-card" role="alertdialog" aria-modal="true">
        <div class="head">This prompt was blocked</div>
        <div class="body">
          <p>It appears to ask for something ${options.orgName} does not permit AI tools
             to be used for.</p>
          <div class="policy"></div>
          <p class="why"></p>
          <p class="note"></p>
          <div class="review" hidden>
            <label>If you believe this is wrong, tell a reviewer why:</label>
            <textarea data-act="reason" rows="3" placeholder="e.g. I was asking how to defend our own systems"></textarea>
            <label class="optin"><input type="checkbox" data-act="opt-in" />
              Include the exact text I was blocked on, so a person can review it.</label>
          </div>
        </div>
        <div class="foot">
          <button class="ghost" data-act="open-review">Request a review</button>
          <button data-act="send-review" hidden>Send review</button>
          <button data-act="edit">Edit my prompt</button>
        </div>
      </div>

      <div class="box reviews-card">
        <div class="reviews-head">
          <span>My Reviews</span>
          <span style="font-size: 12px; font-weight: 500; color: #64748b;">Recent</span>
        </div>
        <div class="reviews-body" data-ref="reviews-list">
          <div class="empty-reviews">Loading reviews...</div>
        </div>
      </div>
    </div>
  `;

  scrim.querySelector('.policy')!.textContent = options.label;

  const ex = explain('ethics', options.category);
  scrim.querySelector('.why')!.textContent = ex.why;
  scrim.querySelector('.note')!.textContent = ex.note;

  const reviewsContainer = scrim.querySelector<HTMLDivElement>('[data-ref="reviews-list"]')!;

  const renderReviewList = (items: ReviewItem[]) => {
    if (!items || items.length === 0) {
      reviewsContainer.innerHTML = '<div class="empty-reviews">No recent review requests.</div>';
      return;
    }
    reviewsContainer.innerHTML = '';
    for (const item of items) {
      const card = document.createElement('div');
      card.className = 'review-item';

      const header = document.createElement('div');
      header.className = 'review-header';

      const title = document.createElement('span');
      title.className = 'review-title';
      const catText = item.category ? item.category.replace(/_/g, ' ') : (item.display_name || 'Ethics Review');
      title.textContent = catText.charAt(0).toUpperCase() + catText.slice(1);

      const statusBadge = document.createElement('span');
      const st = (item.status || item.access_state || 'pending').toLowerCase();
      statusBadge.className = `status-badge status-${st}`;
      statusBadge.textContent = st === 'pending' || st === 'in_review' ? 'In Review'
        : st === 'approved' || st === 'overturned' ? 'Approved'
        : st === 'blocked' || st === 'upheld' ? 'Blocked'
        : st;

      header.append(title, statusBadge);
      card.append(header);

      const userReason = item.employee_reason || item.reason;
      if (userReason) {
        const desc = document.createElement('div');
        desc.className = 'review-desc';
        desc.textContent = userReason;
        card.append(desc);
      }

      if (item.admin_note) {
        const note = document.createElement('div');
        note.className = 'review-note';
        note.textContent = `Note: ${item.admin_note}`;
        card.append(note);
      } else if (item.remediation_guidance) {
        const guidance = document.createElement('div');
        guidance.className = 'review-note';
        guidance.textContent = item.remediation_guidance;
        card.append(guidance);
      }

      reviewsContainer.append(card);
    }
  };

  if (options.reviews) {
    renderReviewList(options.reviews);
  } else if (options.fetchReviews) {
    options.fetchReviews()
      .then((items) => renderReviewList(items))
      .catch(() => renderReviewList([]));
  } else {
    renderReviewList([]);
  }

  const review = scrim.querySelector<HTMLDivElement>('.review')!;
  const sendBtn = scrim.querySelector<HTMLButtonElement>('[data-act="send-review"]')!;
  const openBtn = scrim.querySelector<HTMLButtonElement>('[data-act="open-review"]')!;
  let reason = '';
  scrim.querySelector('[data-act="reason"]')!.addEventListener('input', (e) => {
    reason = (e.target as HTMLTextAreaElement).value;
  });
  openBtn.addEventListener('click', () => { review.hidden = false; openBtn.hidden = true; sendBtn.hidden = false; });
  sendBtn.addEventListener('click', () => {
    const optIn = scrim.querySelector<HTMLInputElement>('[data-act="opt-in"]')!.checked;
    options.onRequestReview(reason, optIn ? options.promptText : undefined);
    hideEthicsModal();
  });

  scrim.querySelector('[data-act="edit"]')!.addEventListener('click', () => {
    hideEthicsModal();
    options.onEdit();
  });

  root.append(style, scrim);
  document.documentElement.append(host);
}

/**
 * Shown when an overturned appeal grants a one-time pass on this exact prompt.
 * The gate already stopped the current send, so — per decision #8 (the user
 * always presses Send) — we tell them to press Send again; the approved hash
 * then lets it through, once.
 */
export function showReviewApprovedModal(onClose: () => void): void {
  hideEthicsModal();
  const host = document.createElement('div');
  host.setAttribute(HOST_ATTR, 'ethics-modal');
  const root = host.attachShadow({ mode: 'open' });
  const style = document.createElement('style');
  style.textContent = `
    .scrim { position: fixed; inset: 0; z-index: 2147483647; display: grid;
             place-items: center; background: rgb(15 23 42 / 55%); }
    .box { max-width: 460px; background: #fff; border-radius: 12px; overflow: hidden;
           font: 15px/1.5 system-ui, sans-serif; box-shadow: 0 20px 50px rgb(0 0 0 / 30%); }
    .head { background: #15803d; color: #fff; padding: 16px 20px; font-weight: 600; }
    .body { padding: 20px; color: #0f172a; }
    .foot { padding: 0 20px 20px; display: flex; justify-content: flex-end; }
    button { border: none; border-radius: 6px; padding: 9px 16px; cursor: pointer;
             background: #15803d; color: #fff; font-size: 14px; }
  `;
  const scrim = document.createElement('div');
  scrim.className = 'scrim';
  scrim.innerHTML = `
    <div class="box" role="alertdialog" aria-modal="true">
      <div class="head">Review approved</div>
      <div class="body"><p>Your review was approved. <strong>Press Send again</strong> to send this
        prompt once — this is a one-time pass for this exact prompt.</p></div>
      <div class="foot"><button data-act="ok">OK</button></div>
    </div>
  `;
  scrim.querySelector('[data-act="ok"]')!.addEventListener('click', () => { hideEthicsModal(); onClose(); });
  root.append(style, scrim);
  document.documentElement.append(host);
}
