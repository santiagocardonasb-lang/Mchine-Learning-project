// CRISP-DM tabs on the presentation page (WAI-ARIA tabs pattern). Without this script every phase stays visible.
(function () {
  const tablist = document.querySelector('.phase-tabs');
  if (!tablist) return;
  const tabs = Array.from(tablist.querySelectorAll('[role="tab"]'));
  const panel = tab => document.getElementById(tab.getAttribute('aria-controls'));

  function select(tab, focus) {
    tabs.forEach(t => {
      const on = t === tab;
      t.setAttribute('aria-selected', String(on));
      t.tabIndex = on ? 0 : -1;
      panel(t).hidden = !on;
    });
    if (focus) tab.focus();
  }

  tablist.addEventListener('click', e => {
    const tab = e.target.closest('[role="tab"]');
    if (tab) select(tab);
  });

  tablist.addEventListener('keydown', e => {
    const i = tabs.indexOf(document.activeElement);
    const next = {ArrowRight: i + 1, ArrowLeft: i - 1, Home: 0, End: tabs.length - 1}[e.key];
    if (i < 0 || next === undefined) return;
    e.preventDefault();
    select(tabs[(next + tabs.length) % tabs.length], true);
  });

  // A link such as /#phase-deployment opens that phase.
  const fromHash = tabs.find(t => '#' + t.getAttribute('aria-controls') === location.hash);
  select(fromHash || tabs[0]);
  tablist.hidden = false;
  if (fromHash) document.getElementById('phases').scrollIntoView();
})();
