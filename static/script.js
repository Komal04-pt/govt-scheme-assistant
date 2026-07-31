let SCHEMES_DATABASE = [];
let activeTab = 'dashboard';
let currentGlobalState = 'ALL';
let currentCatalogCat = 'ALL';
let sessionId = null;

const chatEl = document.getElementById('chat');
const inputEl = document.getElementById('messageInput');
const sendBtn = document.getElementById('sendBtn');
const quickRepliesEl = document.getElementById('quickReplies');

const DEFAULT_QUICK_REPLIES = ['Bihar Student Credit Card', 'PM Kisan Scheme', 'Old Age Pension Eligibility'];

const STATE_LOOKUP = {
  'BR': ['BR', 'BIHAR'],
  'RJ': ['RJ', 'RAJASTHAN'],
  'UP': ['UP', 'UTTAR PRADESH'],
  'MP': ['MP', 'MADHYA PRADESH'],
  'DL': ['DL', 'DELHI'],
  'MH': ['MH', 'MAHARASHTRA'],
  'KA': ['KA', 'KARNATAKA'],
  'WB': ['WB', 'WEST BENGAL']
};

const STATE_NAMES = {
  'BR': 'Bihar',
  'RJ': 'Rajasthan',
  'UP': 'Uttar Pradesh',
  'MP': 'Madhya Pradesh',
  'DL': 'Delhi',
  'MH': 'Maharashtra',
  'KA': 'Karnataka',
  'WB': 'West Bengal'
};

const CENTRAL_KEYWORDS = ['CENTRAL', 'ALL', 'ALL INDIA', 'NATIONAL', 'INDIA'];

function stopSpeech() {
  if ('speechSynthesis' in window) {
    window.speechSynthesis.cancel();
  }
}

function getBookmarks() {
  try {
    return JSON.parse(localStorage.getItem('janseva_bookmarks') || '[]');
  } catch (e) {
    return [];
  }
}

function isBookmarked(schemeId) {
  const bookmarks = getBookmarks();
  return bookmarks.some(id => String(id) === String(schemeId));
}

function toggleBookmark(event, schemeId) {
  if (event) event.stopPropagation();
  let bookmarks = getBookmarks();
  const strId = String(schemeId);

  if (bookmarks.some(id => String(id) === strId)) {
    bookmarks = bookmarks.filter(id => String(id) !== strId);
  } else {
    bookmarks.push(strId);
  }

  localStorage.setItem('janseva_bookmarks', JSON.stringify(bookmarks));
  
  if (activeTab === 'schemes') renderCatalog();
  if (activeTab === 'states') selectStatePortal(currentGlobalState === 'ALL' ? 'BR' : currentGlobalState);
}

function highlightText(text, query) {
  if (!text) return '';
  if (typeof text !== 'string') text = String(text);
  if (!query || query.trim() === '') return text;

  const safeQuery = query.replace(/[.*+?^${}()|[\]\\]/g, '\\$&');
  const regex = new RegExp(`(${safeQuery})`, 'gi');
  return text.replace(regex, '<mark class="bg-yellow-200 text-yellow-900 font-semibold px-0.5 rounded">$1</mark>');
}

async function fetchSchemesFromBackend() {
  try {
    const res = await fetch('/schemes.json');
    if (!res.ok) {
      const apiRes = await fetch('/api/schemes');
      SCHEMES_DATABASE = await apiRes.json();
    } else {
      SCHEMES_DATABASE = await res.json();
    }
  } catch (err) {
    SCHEMES_DATABASE = [];
  }

  const countEl = document.getElementById('dashTotalCount');
  if (countEl) countEl.innerText = SCHEMES_DATABASE.length;

  if (activeTab === 'schemes') renderCatalog();
  if (activeTab === 'states') selectStatePortal(currentGlobalState === 'ALL' ? 'BR' : currentGlobalState);
}

function switchTab(tabId) {
  stopSpeech();
  activeTab = tabId;
  document.querySelectorAll('.page-section').forEach(p => p.classList.remove('active-page'));
  document.querySelectorAll('.nav-link').forEach(n => n.classList.remove('active'));

  const activePage = document.getElementById(`page-${tabId}`);
  const activeNav = document.getElementById(`tab-${tabId}`);
  
  if (activePage) activePage.classList.add('active-page');
  if (activeNav) activeNav.classList.add('active');

  if (tabId === 'schemes') renderCatalog();
  if (tabId === 'states') selectStatePortal(currentGlobalState === 'ALL' ? 'BR' : currentGlobalState);
}

function onGlobalStateChange() {
  const stateSelect = document.getElementById('globalStateSelect');
  if (stateSelect) currentGlobalState = stateSelect.value;
  renderCatalog();
}

function isSchemeMatchState(scheme, targetStateCode) {
  if (!targetStateCode || targetStateCode === 'ALL') return true;

  const rawLocation = (scheme.location || scheme.eligibility?.location || scheme.state || 'CENTRAL').toString().toUpperCase().trim();

  if (CENTRAL_KEYWORDS.includes(rawLocation)) return true;

  const validNames = STATE_LOOKUP[targetStateCode] || [targetStateCode.toUpperCase()];
  return validNames.some(val => rawLocation.includes(val) || val.includes(rawLocation));
}

function buildSchemeCardHtml(scheme, styleVariant, searchVal = '') {
  const rawLoc = (scheme.location || scheme.eligibility?.location || scheme.state || 'CENTRAL').toString().toUpperCase().trim();
  const isCentral = CENTRAL_KEYWORDS.includes(rawLoc);

  const badgeClass = isCentral
    ? 'text-[10px] px-2 py-0.5 rounded uppercase font-semibold border border-slate-200 bg-slate-100 text-slate-700'
    : 'text-[10px] px-2 py-0.5 rounded uppercase font-bold border border-emerald-200 bg-emerald-100 text-emerald-800';

  const ctaLabel = styleVariant === 'state' ? 'Apply →' : 'Details →';
  const ctaClass = styleVariant === 'state' ? 'text-xs text-emerald-800 font-semibold' : 'text-xs text-blue-600 font-semibold';

  const schemeTitle = scheme.name || scheme.title || "Government Scheme";
  const schemeDesc = scheme.description || scheme.desc || "";
  const schemeBenefit = scheme.benefits || scheme.benefit || "Financial / Welfare Benefit";
  const schemeState = isCentral ? 'CENTRAL' : (STATE_NAMES[rawLoc] || rawLoc);
  
  const bookmarked = isBookmarked(scheme.id);

  const highlightedTitle = highlightText(schemeTitle, searchVal);
  const highlightedDesc = highlightText(schemeDesc, searchVal);
  const highlightedBenefit = highlightText(schemeBenefit, searchVal);

  return `
    <div>
      <div class="flex justify-between items-center mb-2">
        <div class="flex items-center gap-1.5 flex-wrap">
          <span class="text-[10px] font-bold uppercase tracking-wider bg-purple-50 text-purple-700 border border-purple-200 px-2 py-0.5 rounded">${scheme.category || 'General'}</span>
          <span class="${badgeClass}">${schemeState}</span>
        </div>
        <button onclick="toggleBookmark(event, '${scheme.id}')" class="text-xs font-semibold px-2 py-0.5 rounded transition ${bookmarked ? 'bg-amber-100 text-amber-700 hover:bg-amber-200' : 'bg-slate-100 text-slate-400 hover:text-slate-600'}" title="${bookmarked ? 'Remove Bookmark' : 'Save Scheme'}">
          ${bookmarked ? '★ Saved' : '☆ Save'}
        </button>
      </div>
      <h4 class="font-bold text-slate-800 text-sm">${highlightedTitle}</h4>
      <p class="text-xs text-slate-500 mt-1 ${styleVariant === 'state' ? '' : 'line-clamp-2'}">${highlightedDesc}</p>
    </div>
    <div class="mt-4 pt-3 border-t border-slate-100 flex justify-between items-center text-xs">
      <span class="font-bold text-emerald-700 line-clamp-1">${highlightedBenefit}</span>
      <span class="${ctaClass}">${ctaLabel}</span>
    </div>
  `;
}

function renderCatalog() {
  const container = document.getElementById('catalogSchemesGrid');
  if (!container) return;

  const searchVal = document.getElementById('searchInput') ? document.getElementById('searchInput').value.toLowerCase().trim() : '';

  const filtered = SCHEMES_DATABASE.filter(s => {
    if (currentCatalogCat === 'Saved') {
      return isBookmarked(s.id);
    }

    const matchState = isSchemeMatchState(s, currentGlobalState);
    
    let matchCat = (currentCatalogCat === 'ALL');
    if (!matchCat) {
      if (currentCatalogCat === 'Youth' && (s.category === 'Youth' || s.category === 'Education')) matchCat = true;
      else if (currentCatalogCat === 'Women' && (s.category === 'Women' || s.category === 'Welfare')) matchCat = true;
      else if (s.category && s.category.toLowerCase().includes(currentCatalogCat.toLowerCase())) matchCat = true;
    }

    const sTitle = s.name || s.title || '';
    const sDesc = s.description || s.desc || '';
    const sBenefit = s.benefits || s.benefit || '';
    const matchSearch = !searchVal || 
      sTitle.toLowerCase().includes(searchVal) || 
      sDesc.toLowerCase().includes(searchVal) || 
      sBenefit.toLowerCase().includes(searchVal);
    
    return matchState && matchCat && matchSearch;
  });

  if (filtered.length === 0) {
    const emptyMsg = currentCatalogCat === 'Saved' 
      ? 'Aapne abhi tak koi scheme bookmark nahi ki hai. ☆ Save button par click karke save karein!'
      : 'No schemes found matching criteria.';
    container.innerHTML = `<p class="col-span-3 text-center text-xs text-slate-400 py-10">${emptyMsg}</p>`;
    return;
  }

  container.innerHTML = '';
  filtered.forEach((scheme) => {
    const card = document.createElement('div');
    card.className = "scheme-card bg-white border border-slate-200 rounded-xl p-4 shadow-sm flex flex-col justify-between cursor-pointer hover:shadow-md transition";
    card.onclick = () => openModal(scheme.id);
    card.innerHTML = buildSchemeCardHtml(scheme, 'catalog', searchVal);
    container.appendChild(card);
  });
}

function setCatalogCat(cat, btnElement) {
  currentCatalogCat = cat;

  const buttons = document.querySelectorAll('.cat-filter-btn, .category-btn');
  buttons.forEach(btn => {
    btn.classList.remove('active');
  });

  if (btnElement) {
    btnElement.classList.add('active');
  }

  renderCatalog();
}

function onSearchChange() {
  renderCatalog();
}

function filterByCategory(cat) {
  currentCatalogCat = cat;
  switchTab('schemes');
  
  const buttons = document.querySelectorAll('.cat-filter-btn, .category-btn');
  buttons.forEach(btn => {
    if (btn.innerText.toLowerCase().includes(cat.toLowerCase())) {
      setCatalogCat(cat, btn);
    }
  });
}

function selectStatePortal(stateCode) {
  currentGlobalState = stateCode;

  const stateSelect = document.getElementById('globalStateSelect');
  if (stateSelect) stateSelect.value = stateCode;

  const container = document.getElementById('stateSpecificGrid');
  if (!container) return;

  document.querySelectorAll('.state-btn').forEach(btn => {
    btn.classList.remove('border-emerald-600', 'bg-emerald-50', 'ring-2', 'ring-emerald-500/20');
    btn.classList.add('border-slate-200', 'bg-slate-50');
  });

  const activeCard = document.getElementById(`state-card-${stateCode}`);
  if (activeCard) {
    activeCard.classList.remove('border-slate-200', 'bg-slate-50');
    activeCard.classList.add('border-emerald-600', 'bg-emerald-50', 'ring-2', 'ring-emerald-500/20');
  }

  const titleEl = document.getElementById('statePortalTitle');
  if (titleEl) titleEl.innerText = `${STATE_NAMES[stateCode] || stateCode} & Central Schemes`;

  const stateSchemes = SCHEMES_DATABASE
    .filter(s => isSchemeMatchState(s, stateCode))
    .sort((a, b) => {
      const rawLocA = (a.location || a.eligibility?.location || a.state || 'CENTRAL').toString().toUpperCase().trim();
      const rawLocB = (b.location || b.eligibility?.location || b.state || 'CENTRAL').toString().toUpperCase().trim();
      const isCentralA = CENTRAL_KEYWORDS.includes(rawLocA);
      const isCentralB = CENTRAL_KEYWORDS.includes(rawLocB);
      return isCentralA - isCentralB;
    });

  container.innerHTML = '';
  if (stateSchemes.length === 0) {
    container.innerHTML = `<p class="col-span-3 text-center text-xs text-slate-400 py-10">No schemes found for this selection.</p>`;
    return;
  }

  stateSchemes.forEach((scheme) => {
    const card = document.createElement('div');
    card.className = "scheme-card bg-white border border-slate-200 rounded-xl p-4 shadow-sm flex flex-col justify-between cursor-pointer hover:shadow-md transition";
    card.onclick = () => openModal(scheme.id);
    card.innerHTML = buildSchemeCardHtml(scheme, 'state');
    container.appendChild(card);
  });
}

function formatEligibility(data) {
  if (!data) return '<p class="text-slate-500 text-[11px]">Eligible citizens meeting state/central guidelines.</p>';
  
  let parsedObj = {};

  if (typeof data === 'object' && !Array.isArray(data)) {
    parsedObj = data;
  } else if (typeof data === 'string') {
    try {
      parsedObj = JSON.parse(data);
    } catch (e) {
      const items = {};
      data.split(';').forEach(pair => {
        const [k, v] = pair.split(':');
        if (k && v) items[k.trim().toLowerCase()] = v.trim();
      });
      if (Object.keys(items).length > 0) parsedObj = items;
      else return `<ul class="list-disc list-inside space-y-1 text-slate-600 text-[11px]"><li>${data.trim()}</li></ul>`;
    }
  }

  const bullets = [];

  if (parsedObj.location && parsedObj.location !== 'CENTRAL') {
    bullets.push(`<strong>Location:</strong> ${parsedObj.location}`);
  }

  if (parsedObj.age_min || parsedObj['age min'] || parsedObj.age_max || parsedObj['age max']) {
    const min = parsedObj.age_min || parsedObj['age min'] || '18';
    const max = parsedObj.age_max || parsedObj['age max'] || 'No upper limit';
    bullets.push(`<strong>Age Limit:</strong> ${min} to ${max} years`);
  }

  if (parsedObj.income_max || parsedObj['income max'] || parsedObj.income) {
    const inc = parsedObj.income_max || parsedObj['income max'] || parsedObj.income;
    const formattedInc = isNaN(inc) ? inc : `₹${Number(inc).toLocaleString('en-IN')} / year`;
    bullets.push(`<strong>Income Threshold:</strong> Max ${formattedInc}`);
  }

  if (parsedObj.occupation) {
    let occ = parsedObj.occupation;
    if (typeof occ === 'string') {
      try { occ = JSON.parse(occ); } catch(e) {}
    }
    const occStr = Array.isArray(occ) ? occ.map(o => o.replace(/_/g, ' ')).join(', ') : occ.toString().replace(/_/g, ' ');
    bullets.push(`<strong>Target Occupation:</strong> ${occStr}`);
  }

  if (parsedObj.exclusions) {
    let exc = parsedObj.exclusions;
    if (typeof exc === 'string') {
      try { exc = JSON.parse(exc); } catch(e) {}
    }
    
    const isNotEmpty = Array.isArray(exc) ? exc.length > 0 : (exc && exc.toString().trim() !== '' && exc.toString().toLowerCase() !== 'none');
    
    if (isNotEmpty) {
      const excStr = Array.isArray(exc) ? exc.map(e => e.replace(/_/g, ' ')).join(', ') : exc.toString().replace(/_/g, ' ');
      bullets.push(`<strong>Exclusions:</strong> ${excStr}`);
    }
  }

  if (parsedObj.gender && parsedObj.gender.toLowerCase() !== 'any') {
    bullets.push(`<strong>Gender Preference:</strong> ${parsedObj.gender}`);
  }

  if (bullets.length === 0) {
    return `<ul class="list-disc list-inside space-y-1 text-slate-600 text-[11px]"><li>${typeof data === 'string' ? data : JSON.stringify(data)}</li></ul>`;
  }

  return `<ul class="list-disc list-inside space-y-1 text-slate-700 text-[11px]">${bullets.map(b => `<li>${b}</li>`).join('')}</ul>`;
}

function formatDocumentsList(data) {
  if (!data) return '<ul class="list-disc list-inside text-slate-600 text-[11px]"><li>Check official portal for specific required documents.</li></ul>';

  let list = [];
  if (Array.isArray(data)) {
    list = data;
  } else if (typeof data === 'string') {
    if (data.startsWith('[') && data.endsWith(']')) {
      try { list = JSON.parse(data); } catch(e) { list = data.split(','); }
    } else {
      list = data.split(',');
    }
  }

  const cleanList = list.map(item => String(item).trim()).filter(Boolean);
  
  if (cleanList.length === 0) {
    return '<ul class="list-disc list-inside text-slate-600 text-[11px]"><li>Check official portal for specific required documents.</li></ul>';
  }

  return `<ul class="list-disc list-inside space-y-1 text-slate-700 text-[11px]">${cleanList.map(doc => `<li>${doc}</li>`).join('')}</ul>`;
}

function openModal(schemeId) {
  const scheme = SCHEMES_DATABASE.find(s => String(s.id) === String(schemeId));
  if (!scheme) return;

  const modalContent = document.getElementById('modalContent');
  const modal = document.getElementById('schemeModal');

  if (modal) modal.classList.remove('hidden');

  const title = scheme.name || scheme.title || "Government Scheme";
  const desc = scheme.description || scheme.desc || "";
  const benefit = scheme.benefits || scheme.benefit || "Financial / Welfare Benefit";
  
  const rawEligibility = scheme.eligibility_desc || scheme.eligibility_criteria || scheme.eligibility?.criteria || scheme.eligibility;
  const eligibilityHtml = formatEligibility(rawEligibility);

  const rawDocs = scheme.documents_required || scheme.documents || scheme.required_documents || scheme.docs;
  const docsHtml = formatDocumentsList(rawDocs);

  const applyUrl = scheme.apply_url || `https://www.google.com/search?q=${encodeURIComponent(title + " official portal apply online")}`;
  const bookmarked = isBookmarked(scheme.id);

  if (modalContent) {
    modalContent.innerHTML = `
      <div class="flex justify-between items-center pr-6 mb-2">
        <span class="text-[10px] font-bold uppercase text-emerald-700 bg-emerald-100 px-2.5 py-1 rounded-md">${scheme.category || 'General'}</span>
        
        <button onclick="toggleBookmark(event, '${scheme.id}'); openModal('${scheme.id}');" class="text-xs font-semibold px-2.5 py-1 rounded-md transition ${bookmarked ? 'bg-amber-100 text-amber-800 hover:bg-amber-200' : 'bg-slate-100 text-slate-600 hover:bg-slate-200'}">
          ${bookmarked ? '★ Saved' : '☆ Save Scheme'}
        </button>
      </div>

      <h3 class="text-base sm:text-lg font-extrabold text-slate-900 leading-snug">${title}</h3>
      <p class="text-xs text-slate-600 mt-1 leading-relaxed">${desc}</p>
      
      <div class="my-3 bg-emerald-50/90 border border-emerald-200 p-3 rounded-xl text-xs">
        <p class="font-bold text-emerald-800 flex items-center gap-1.5">
          <i class="fa-solid fa-gift text-emerald-600"></i> Key Benefit:
        </p>
        <p class="text-emerald-950 font-bold text-xs sm:text-sm mt-0.5 leading-snug">${benefit}</p>
      </div>

      <div class="space-y-3 my-3">
        <div class="bg-slate-50 p-3 rounded-xl border border-slate-200">
          <strong class="text-slate-900 font-bold text-xs flex items-center gap-1.5 mb-2">
            <i class="fa-solid fa-user-check text-emerald-600"></i> Eligibility Criteria
          </strong>
          ${eligibilityHtml}
        </div>

        <div class="bg-slate-50 p-3 rounded-xl border border-slate-200">
          <strong class="text-slate-900 font-bold text-xs flex items-center gap-1.5 mb-2">
            <i class="fa-solid fa-file-lines text-blue-600"></i> Required Documents
          </strong>
          ${docsHtml}
        </div>
      </div>

      <div class="mt-4 flex flex-col sm:flex-row gap-2">
        <button onclick="askBotAbout('${title.replace(/'/g, "\\'")}')" class="flex-1 bg-emerald-700 hover:bg-emerald-800 text-white text-xs py-2.5 rounded-xl font-bold transition flex items-center justify-center gap-1.5 shadow-sm">
          <i class="fa-solid fa-robot"></i> Ask AI Assistant
        </button>
        <a href="${applyUrl}" target="_blank" rel="noopener noreferrer" class="flex-1 text-center bg-slate-900 hover:bg-slate-800 text-white text-xs py-2.5 rounded-xl font-bold transition flex items-center justify-center gap-1.5 shadow-sm">
          Apply Official Portal <i class="fa-solid fa-arrow-up-right-from-square text-[10px]"></i>
        </a>
      </div>
    `;
  }
}

function closeModal() {
  const modal = document.getElementById('schemeModal');
  if (modal) modal.classList.add('hidden');
}

function openEligibilityModal() {
  const modal = document.getElementById('eligibilityModal');
  if (modal) modal.classList.remove('hidden');
}

function closeEligibilityModal() {
  const modal = document.getElementById('eligibilityModal');
  if (modal) modal.classList.add('hidden');
}

function resetEligibilityForm() {
  const form = document.getElementById('eligibilityForm');
  if (form) form.reset();
  
  const resultsDiv = document.getElementById('eligibilityResults');
  if (resultsDiv) resultsDiv.classList.add('hidden');
  
  const listDiv = document.getElementById('matchedSchemesList');
  if (listDiv) listDiv.innerHTML = '';
}

async function calculateEligibility(event) {
  event.preventDefault();
  
  const age = document.getElementById('userAge') ? document.getElementById('userAge').value : 0;
  const gender = document.getElementById('userGender') ? document.getElementById('userGender').value : 'any';
  const state = document.getElementById('userState') ? document.getElementById('userState').value : 'ALL';
  const occupation = document.getElementById('userOccupation') ? document.getElementById('userOccupation').value : 'any';
  const income = document.getElementById('userIncome') ? document.getElementById('userIncome').value : 9999999;

  const resultsDiv = document.getElementById('eligibilityResults');
  const listDiv = document.getElementById('matchedSchemesList');
  const countHeader = document.getElementById('resultsCountHeader');

  if (resultsDiv) resultsDiv.classList.remove('hidden');
  if (listDiv) listDiv.innerHTML = `<p class="text-center text-slate-400 py-4"><i class="fa-solid fa-spinner fa-spin text-emerald-600 mr-2"></i>Checking eligible schemes...</p>`;

  try {
    const response = await fetch('/api/check-eligibility', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ age, gender, state, occupation, income })
    });
    
    const data = await response.json();
    
    if (data.success && data.matched_schemes && data.matched_schemes.length > 0) {
      if (countHeader) countHeader.innerText = `${data.matched_schemes.length} Eligible Schemes Found`;
      
      listDiv.innerHTML = data.matched_schemes.map(s => `
        <div onclick="closeEligibilityModal(); openModal('${s.id}')" class="p-2.5 bg-slate-50 border border-slate-200 rounded-lg cursor-pointer hover:border-emerald-500 hover:bg-emerald-50/30 transition flex justify-between items-center">
          <div>
            <h5 class="font-bold text-slate-800 text-xs">${s.name || s.title}</h5>
            <p class="text-[10px] text-emerald-700 font-semibold">${s.benefits || s.benefit || 'Welfare Scheme'}</p>
          </div>
          <span class="text-[10px] bg-emerald-100 text-emerald-800 px-2 py-0.5 rounded font-bold">Apply →</span>
        </div>
      `).join('');
    } else {
      if (countHeader) countHeader.innerText = 'No Schemes Found';
      listDiv.innerHTML = `<p class="text-center text-slate-500 py-3">No direct schemes found matching your criteria. Try adjusting the income or state selection.</p>`;
    }
  } catch (err) {
    if (listDiv) listDiv.innerHTML = `<p class="text-center text-red-500 py-3">Error fetching eligibility. Please try again.</p>`;
  }
}

function askBotAbout(schemeName) {
  closeModal();
  switchTab('ai');
  const prompt = `Tell me about eligibility and detailed application steps for ${schemeName}`;
  if (inputEl) inputEl.value = prompt;
  sendMessage();
}

function addMessage(text, sender, isLoading = false, audioUrl = null) {
  if (!chatEl) return;

  // Purani speech ko stop kar do naya message aane par
  stopSpeech();

  const wrapper = document.createElement('div');
  wrapper.className = `flex ${sender === 'user' ? 'justify-end' : 'justify-start'} mb-2`;

  const div = document.createElement('div');
  div.className = `msg ${sender} max-w-[85%] p-3 rounded-2xl text-xs md:text-sm leading-relaxed shadow-sm ` +
    (sender === 'user' ? 'bg-slate-900 text-white rounded-tr-none' : 'bg-white border border-slate-200 text-slate-800 rounded-tl-none msg-content');

  if (isLoading) {
    div.classList.add('italic', 'text-slate-400');
    div.textContent = text;
  } else if (sender === 'bot') {
    div.innerHTML = typeof marked !== 'undefined' ? marked.parse(text) : text;
  } else {
    div.textContent = text;
  }

  // Audio Handler with Play/Stop Toggle Control
  if (sender === 'bot' && !isLoading) {
    const audioContainer = document.createElement('div');
    audioContainer.className = 'mt-3 pt-2 border-t border-slate-100 flex items-center gap-2';

    if (audioUrl && audioUrl.trim() !== '') {
      const audioEl = document.createElement('audio');
      audioEl.className = 'w-full h-8';
      audioEl.controls = true;
      audioEl.src = audioUrl;
      audioContainer.appendChild(audioEl);
      audioEl.play().catch(e => console.log("Autoplay blocked by browser policy"));
    } else {
      const speakBtn = document.createElement('button');
      speakBtn.className = 'text-xs bg-emerald-100 hover:bg-emerald-200 text-emerald-800 px-3 py-1 rounded-full font-bold flex items-center gap-1.5 transition';
      
      const setBtnState = (isPlaying) => {
        if (isPlaying) {
          speakBtn.innerHTML = '⏹️ Stop Listening';
          speakBtn.className = 'text-xs bg-red-100 hover:bg-red-200 text-red-800 px-3 py-1 rounded-full font-bold flex items-center gap-1.5 transition';
        } else {
          speakBtn.innerHTML = '🔊 Listen Response';
          speakBtn.className = 'text-xs bg-emerald-100 hover:bg-emerald-200 text-emerald-800 px-3 py-1 rounded-full font-bold flex items-center gap-1.5 transition';
        }
      };

      setBtnState(false);
      
      const cleanText = div.innerText || div.textContent;
      
      const toggleSpeech = () => {
        if (!('speechSynthesis' in window)) return;

        if (window.speechSynthesis.speaking) {
          stopSpeech();
          setBtnState(false);
        } else {
          stopSpeech();
          const utterance = new SpeechSynthesisUtterance(cleanText);

          // Language script detection (Devanagari \u0900-\u097F)
          const isHindi = /[\u0900-\u097F]/.test(cleanText);
          utterance.lang = isHindi ? 'hi-IN' : 'en-IN';

          const voices = window.speechSynthesis.getVoices();
          if (isHindi) {
            const hindiVoice = voices.find(v => v.lang.includes('hi') || v.name.includes('Hindi'));
            if (hindiVoice) utterance.voice = hindiVoice;
          }

          utterance.onend = () => setBtnState(false);
          utterance.onerror = () => setBtnState(false);

          window.speechSynthesis.speak(utterance);
          setBtnState(true);
        }
      };

      speakBtn.onclick = toggleSpeech;
      audioContainer.appendChild(speakBtn);

      // Auto start speech playback
      toggleSpeech();
    }

    div.appendChild(audioContainer);
  }

  wrapper.appendChild(div);
  chatEl.appendChild(wrapper);
  chatEl.scrollTop = chatEl.scrollHeight;
  return wrapper;
}

let mediaRecorder = null;
let audioChunks = [];
let isRecording = false;

async function toggleRecording() {
  const micBtn = document.getElementById('micBtn');

  if (!isRecording) {
    try {
      stopSpeech();
      const stream = await navigator.mediaDevices.getUserMedia({ 
        audio: {
          echoCancellation: true,
          noiseSuppression: true,
          autoGainControl: true
        } 
      });

      let options = {};
      if (typeof MediaRecorder !== 'undefined') {
        if (MediaRecorder.isTypeSupported('audio/webm')) {
          options = { mimeType: 'audio/webm' };
        } else if (MediaRecorder.isTypeSupported('audio/mp4')) {
          options = { mimeType: 'audio/mp4' };
        } else if (MediaRecorder.isTypeSupported('audio/wav')) {
          options = { mimeType: 'audio/wav' };
        }
      }

      mediaRecorder = new MediaRecorder(stream, options);
      audioChunks = [];

      mediaRecorder.ondataavailable = (e) => {
        if (e.data && e.data.size > 0) audioChunks.push(e.data);
      };

      mediaRecorder.onstop = () => {
        const mimeType = mediaRecorder.mimeType || 'audio/webm';
        const audioBlob = new Blob(audioChunks, { type: mimeType });
        stream.getTracks().forEach(track => track.stop());

        if (audioBlob.size > 300) {
          sendVoiceMessage(audioBlob);
        } else {
          addMessage('Voice input was too short. Please speak again.', 'bot');
        }
      };

      mediaRecorder.start(200);
      isRecording = true;

      if (micBtn) {
        micBtn.classList.add('bg-red-600', 'text-white', 'animate-pulse');
        micBtn.innerText = "⏹️";
      }
    } catch (err) {
      alert('Microphone access denied or not supported on this device.');
    }
  } else {
    if (mediaRecorder && mediaRecorder.state !== 'inactive') mediaRecorder.stop();
    isRecording = false;

    if (micBtn) {
      micBtn.classList.remove('bg-red-600', 'text-white', 'animate-pulse');
      micBtn.innerText = "🎤";
    }
  }
}

async function sendVoiceMessage(audioBlob) {
  const micBtn = document.getElementById('micBtn');
  if (sendBtn) sendBtn.disabled = true;
  if (micBtn) micBtn.disabled = true;
  
  const loadingMsg = addMessage('Processing voice message...', 'bot', true);

  try {
    const formData = new FormData();
    const ext = audioBlob.type.includes('mp4') ? 'mp4' : (audioBlob.type.includes('wav') ? 'wav' : 'webm');
    formData.append('audio', audioBlob, `recording.${ext}`);
    formData.append('session_id', sessionId || '');

    const res = await fetch('/voice-chat', { method: 'POST', body: formData });
    
    if (!res.ok) {
      const errData = await res.json().catch(() => ({}));
      throw new Error(errData.error || `Server Status ${res.status}`);
    }

    const data = await res.json();
    sessionId = data.session_id;

    if (loadingMsg) loadingMsg.remove();
    
    if (data.transcript && data.transcript.trim().length > 1) {
      addMessage(data.transcript, 'user');
      addMessage(data.reply, 'bot', false, data.audio_url);
    } else {
      addMessage("Sorry, couldn't hear clearly. Please speak again.", 'bot');
    }
  } catch (err) {
    if (loadingMsg) loadingMsg.remove();
    console.error("Voice Processing Error:", err);
    addMessage(`Voice error: ${err.message || 'Server error during transcription.'}`, 'bot');
  } finally {
    if (sendBtn) sendBtn.disabled = false;
    if (micBtn) micBtn.disabled = false;
  }
}

function setQuickReplies(options) {
  if (!quickRepliesEl) return;
  quickRepliesEl.innerHTML = '';
  options.forEach(opt => {
    const btn = document.createElement('button');
    btn.className = 'text-xs bg-slate-100 text-slate-700 border border-slate-300 rounded-full px-3 py-1 hover:bg-slate-200 transition font-medium';
    btn.textContent = opt;
    btn.onclick = () => {
      if (inputEl) inputEl.value = opt;
      sendMessage();
    };
    quickRepliesEl.appendChild(btn);
  });
}

async function sendMessage() {
  stopSpeech();
  if (!inputEl) return;
  const text = inputEl.value.trim();
  if (!text) return;

  addMessage(text, 'user');
  inputEl.value = '';
  if (sendBtn) sendBtn.disabled = true;
  if (quickRepliesEl) quickRepliesEl.innerHTML = '';

  const loadingMsg = addMessage('Thinking...', 'bot', true);

  try {
    const res = await fetch('/chat', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ session_id: sessionId, message: text })
    });
    const data = await res.json();
    sessionId = data.session_id;

    if (loadingMsg) loadingMsg.remove();
    addMessage(data.reply || data.response, 'bot', false, data.audio_url);
  } catch (err) {
    if (loadingMsg) loadingMsg.remove();
    addMessage('AI response error.', 'bot');
  } finally {
    if (sendBtn) sendBtn.disabled = false;
    if (inputEl) inputEl.focus();
  }
}

if (inputEl) {
  inputEl.addEventListener('keypress', (e) => {
    if (e.key === 'Enter') sendMessage();
  });
}

const searchInputEl = document.getElementById('searchInput');
if (searchInputEl) {
  searchInputEl.addEventListener('input', () => {
    onSearchChange();
  });
}

fetchSchemesFromBackend();

if (chatEl && chatEl.children.length === 0) {
  addMessage("Hello! 🙏 I am your JanSeva AI Assistant. Ask me about any central or state scheme.", 'bot');
}
setQuickReplies(DEFAULT_QUICK_REPLIES);