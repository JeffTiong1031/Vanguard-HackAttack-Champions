import { render } from 'preact';
import { useEffect, useState } from 'preact/hooks';
import { getMode, type Mode } from '../../src/mode/mode';
import { toolForHost } from '../../src/policy/lookup';
import type { PolicyRequest, PolicyResponse } from '../../src/policy/messages';
import type { Enrolment, Policy, Tool } from '../../src/policy/types';

function ask(msg: PolicyRequest): Promise<PolicyResponse> {
  return chrome.runtime.sendMessage(msg) as Promise<PolicyResponse>;
}

function Popup() {
  const [enrolment, setEnrolment] = useState<Enrolment | null>(null);
  const [policy, setPolicy] = useState<Policy | null>(null);
  const [host, setHost] = useState('');
  const [mode, setMode] = useState<Mode | null>(null);

  useEffect(() => {
    void chrome.tabs.query({ active: true, currentWindow: true }).then((tabs) => {
      const url = tabs[0]?.url;
      if (url) {
        try { setHost(new URL(url).hostname); } catch { /* ignore */ }
      }
    });

    void ask({ kind: 'policy-get' }).then((r) => {
      if (r.ok) {
        setEnrolment(r.enrolment);
        setPolicy(r.policy);
      }
    });

    void getMode().then(setMode);
  }, []);

  const openOptions = () => chrome.runtime.openOptionsPage();

  if (mode === 'personal') {
    return (
      <div style="width:300px;padding:16px;font:14px/1.5 system-ui,sans-serif">
        <div style="display:flex;align-items:center;gap:12px;margin-bottom:12px">
          <img src="/icon/48.png" style="width:24px;height:24px" alt="" />
          <h1 style="font-size:16px;margin:0">Vanguard</h1>
        </div>
        <p style="color:#0f172a;margin:0 0 6px 0"><strong>Personal mode</strong></p>
        <p style="color:#475569;margin:0">
          {host ? `Protecting sensitive data on ${host}.` : 'Protecting sensitive data on this device.'}
          {' '}Nothing leaves your device.
        </p>
      </div>
    );
  }
  if (mode === null) {
    return (
      <div style="width:300px;padding:16px;font:14px/1.5 system-ui,sans-serif">
        <p style="color:#475569;margin:0 0 12px 0">Choose Personal or Enterprise to get started.</p>
        <button onClick={openOptions} style="width:100%;padding:8px;border:none;
                border-radius:6px;background:#e11d48;color:#fff;cursor:pointer">Open settings</button>
      </div>
    );
  }
  if (!enrolment || !policy) {
    return (
      <div style="width:300px;padding:16px;font:14px/1.5 system-ui,sans-serif">
        <div style="display:flex;align-items:center;gap:12px;margin-bottom:12px">
          <img src="/icon/48.png" style="width:24px;height:24px" alt="" />
          <h1 style="font-size:16px;margin:0">Vanguard</h1>
        </div>
        <p style="color:#475569">Vanguard is not connected to an organisation.</p>
        <button onClick={openOptions} style="width:100%;padding:8px;border:none;
                border-radius:6px;background:#e11d48;color:#fff;cursor:pointer">Connect</button>
      </div>
    );
  }

  const tool = toolForHost(policy, host);

  return (
    <div style="width:300px;padding:0;font:14px/1.5 system-ui,sans-serif">
      <div style="padding:16px;background:#f8fafc;border-bottom:1px solid #e2e8f0;
                  display:flex;align-items:center;justify-content:space-between">
        <div style="display:flex;align-items:center;gap:8px">
          <img src="/icon/48.png" style="width:20px;height:20px" alt="" />
          <h1 style="font-size:14px;margin:0;color:#0f172a">{enrolment.org_name}</h1>
        </div>
        <button onClick={openOptions} style="border:none;background:none;
                color:#64748b;cursor:pointer;font-size:18px" title="Options">⚙</button>
      </div>

      <div style="padding:16px">
        {tool ? (
          <div>
            <div style="display:flex;justify-content:space-between;margin-bottom:8px">
              <strong style="color:#0f172a">{tool.display_name}</strong>
              {tool.status === 'approved' ? (
                <span style="color:#15803d;background:#dcfce7;padding:2px 8px;border-radius:12px;font-size:12px">Approved</span>
              ) : (
                <span style="color:#b45309;background:#fef3c7;padding:2px 8px;border-radius:12px;font-size:12px">Unapproved</span>
              )}
            </div>
            <p style="color:#475569;font-size:13px;margin:0 0 16px 0">
              {tool.status === 'approved'
                ? 'Your organisation approves this tool for work.'
                : 'This tool is not approved for work. You can still use it, but Vanguard will warn you.'}
            </p>
          </div>
        ) : (
          <p style="color:#475569;margin:0 0 16px 0">
            {host ? `Vanguard is active on ${host}.` : 'Vanguard is running.'}
          </p>
        )}

        <div style="border-top:1px solid #e2e8f0;padding-top:12px;margin-top:16px">
          <p style="font-size:12px;color:#64748b;margin:0">
            Department: {enrolment.department}<br />
            Policy v{policy.version}
          </p>
        </div>
      </div>
    </div>
  );
}

render(<Popup />, document.getElementById('root')!);
