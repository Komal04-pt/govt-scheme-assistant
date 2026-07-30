// Global State & Data Store
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

// ================= BOOKMARKING / LOCALSTORAGE LOGIC =================
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

// ================= SEARCH HIGHLIGHTING UTILITY =================
function highlightText(text, query) {
  if (!text) return '';
  if (!query || query.trim() === '') return text;

  const safeQuery = query.replace(/[.*+?^${}()|[\]\\]/g, '\\$&');
  const regex = new RegExp(`(${safeQuery})`, 'gi');
  return text.replace(regex, '<mark class="bg-yellow-200 text-yellow-900 font-semibold px-0.5 rounded">$1</mark>');
}

// Fetch Schemes Data from Backend JSON on Load
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
    console.error("Error loading schemes:", err);
    SCHEMES_DATABASE = [];
  }

  const countEl = document.getElementById('dashTotalCount');
  if (countEl) countEl.innerText = SCHEMES_DATABASE.length;

  if (activeTab === 'schemes') renderCatalog();
  if (activeTab === 'states') selectStatePortal(currentGlobalState === 'ALL' ? 'BR' : currentGlobalState);
}

function switchTab(tabId) {
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

function buildSchemeCardHtml(scheme, styleVariant, searchVal = '') {
  const badgeClass = styleVariant === 'state'
    ? 'text-[9px] font-bold uppercase text-indigo-700 bg-indigo-50 px-2 py-0.5 rounded'
    : 'text-[9px] font-bold uppercase tracking-wider text-emerald-800 bg-emerald-100 px-2 py-0.5 rounded';
  const ctaLabel = styleVariant === 'state' ? 'Apply →' : 'Details →';
  const ctaClass = styleVariant === 'state' ? 'text-xs text-emerald-800 font-semibold' : 'text-xs text-blue-600 font-semibold';

  const schemeTitle = scheme.name || scheme.title || "Government Scheme";
  const schemeDesc = scheme.description || scheme.desc || "";
  const schemeBenefit = scheme.benefits || scheme.benefit || "Financial / Welfare Benefit";
  const schemeState = scheme.eligibility?.location || scheme.state || "CENTRAL";
  
  const bookmarked = isBookmarked(scheme.id);

  const highlightedTitle = highlightText(schemeTitle, searchVal);
  const highlightedDesc = highlightText(schemeDesc, searchVal);
  const highlightedBenefit = highlightText(schemeBenefit, searchVal);

  return `
    <div>
      <div class="flex justify-between items-center mb-2">
        <div class="flex items-center gap-1.5">
          <span class="${badgeClass}">${scheme.category || 'General'}</span>
          <span class="text-[10px] font-bold text-slate-700 bg-slate-100 border border-slate-200 px-2 py-0.5 rounded">${schemeState}</span>
        </div>
        <button onclick="toggleBookmark(event, '${scheme.id}')" class="text-xs font-semibold px-2 py-0.5 rounded transition ${bookmarked ? 'bg-amber-100 text-amber-700 hover:bg-amber-200' : 'bg-slate-100 text-slate-400 hover:text-slate-600'}" title="${bookmarked ? 'Remove Bookmark' : 'Save Scheme'}">
          ${bookmarked ? '★ Saved' : '☆ Save'}
        </button>
      </div>
      <h4 class="font-bold text-slate-800 text-sm">${highlightedTitle}</h4>
      <p class="text-xs text-slate-500 mt-1 ${styleVariant === 'state' ? '' : 'line-clamp-2'}">${highlightedDesc}</p>
    </div>
    <div class="mt-4 pt-3 border-t border-slate-100 flex justify-between items-center text-xs">
      <span class="font-bold text-emerald-700">${highlightedBenefit}</span>
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

    const sState = s.eligibility?.location || s.state || 'CENTRAL';
    const matchState = (currentGlobalState === 'ALL') || (sState === 'CENTRAL') || (sState === currentGlobalState);
    
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

  const buttons = document.querySelectorAll('.cat-filter-btn');
  buttons.forEach(btn => {
    btn.classList.remove('bg-emerald-800', 'text-white');
    btn.classList.add('bg-slate-100', 'text-slate-600');
  });

  if (btnElement) {
    btnElement.classList.remove('bg-slate-100', 'text-slate-600');
    btnElement.classList.add('bg-emerald-800', 'text-white');
  }

  renderCatalog();
}

function onSearchChange() {
  renderCatalog();
}

function filterByCategory(cat) {
  currentCatalogCat = cat;
  switchTab('schemes');
  
  const buttons = document.querySelectorAll('.cat-filter-btn');
  buttons.forEach(btn => {
    if (btn.innerText.toLowerCase().includes(cat.toLowerCase())) {
      setCatalogCat(cat, btn);
    }
  });
}

function selectStatePortal(stateCode) {
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

  const stateNames = { 
    'BR': 'Bihar', 'RJ': 'Rajasthan', 'UP': 'Uttar Pradesh', 
    'MP': 'Madhya Pradesh', 'DL': 'Delhi', 'MH': 'Maharashtra', 
    'KA': 'Karnataka', 'WB': 'West Bengal' 
  };
  
  const titleEl = document.getElementById('statePortalTitle');
  if (titleEl) titleEl.innerText = `${stateNames[stateCode] || stateCode} Schemes`;

  const stateSchemes = SCHEMES_DATABASE.filter(s => {
    const sState = s.eligibility?.location || s.state || 'CENTRAL';
    return sState === stateCode || sState === 'CENTRAL';
  });

  container.innerHTML = '';
  stateSchemes.forEach((scheme) => {
    const card = document.createElement('div');
    card.className = "scheme-card bg-white border border-slate-200 rounded-xl p-4 shadow-sm flex flex-col justify-between cursor-pointer hover:shadow-md transition";
    card.onclick = () => openModal(scheme.id);
    card.innerHTML = buildSchemeCardHtml(scheme, 'state');
    container.appendChild(card);
  });
}

// Helper: Generates realistic documents list if JSON data is short
function getRealisticDocuments(scheme) {
  const rawDocs = scheme.documents_required || scheme.documents;
  if (Array.isArray(rawDocs) && rawDocs.length >= 4) {
    return rawDocs;
  }

  const category = (scheme.category || '').toLowerCase();
  
  if (category.includes('financial') || category.includes('pension') || category.includes('inclusion')) {
    return [
      "Aadhaar Card (Mandatory Identity & Address Proof)",
      "PAN Card / Form 60",
      "Active Bank Account Passbook (Aadhaar Seeded)",
      "2 Recent Passport Size Photographs",
      "Mobile Number linked with Aadhaar",
      "Income / Caste Certificate (If applying under quota)"
    ];
  } else if (category.includes('agri') || category.includes('farmer')) {
    return [
      "Aadhaar Card (Identity Proof)",
      "Land Record / Khatauni Copy (Land ownership proof)",
      "Bank Passbook Details with IFSC Code",
      "Aadhaar-seeded Mobile Number",
      "Self-Declaration / Farmer Registration Card"
    ];
  } else if (category.includes('youth') || category.includes('edu')) {
    return [
      "Aadhaar Card of Applicant & Guardian",
      "Educational Marksheets (10th / 12th / Degree)",
      "Income Certificate issued by Tehsildar/SDM",
      "State Domicile / Residence Certificate",
      "Institution Admission Fee Receipt & Bonafide Certificate",
      "Bank Account Details"
    ];
  } else {
    return [
      "Aadhaar Card (Identity & Address Proof)",
      "Residence / Domicile Certificate",
      "Income Certificate (Family Annual Income)",
      "Bank Account Passbook Copy",
      "Passport Size Photographs (2 Copies)",
      "Active Mobile Number & Email ID"
    ];
  }
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
  const applySteps = scheme.how_to_apply || scheme.eligibility_desc || "Visit official portal or nearest Jan Seva Kendra / Bank Mitra.";

  const applyUrl = scheme.apply_url || `https://www.google.com/search?q=${encodeURIComponent(title + " official portal apply online")}`;
  const bookmarked = isBookmarked(scheme.id);

  // Get realistic comprehensive document checklist
  const docsList = getRealisticDocuments(scheme);

  if (modalContent) {
    modalContent.innerHTML = `
      <div class="flex justify-between items-center pr-6 mb-3">
        <span class="text-[10px] font-bold uppercase text-emerald-700 bg-emerald-100 px-2.5 py-1 rounded">${scheme.category || 'General'}</span>
        
        <button onclick="toggleBookmark(event, '${scheme.id}'); openModal('${scheme.id}');" class="text-xs font-semibold px-2.5 py-1 rounded transition ${bookmarked ? 'bg-amber-100 text-amber-800 hover:bg-amber-200' : 'bg-slate-100 text-slate-600 hover:bg-slate-200'}">
          ${bookmarked ? '★ Saved' : '☆ Save Scheme'}
        </button>
      </div>

      <h3 class="text-lg font-bold text-slate-900">${title}</h3>
      <p class="text-xs text-slate-600 mt-1">${desc}</p>
      
      <div class="my-3 bg-emerald-50 border border-emerald-200 p-3 rounded-xl text-xs">
        <p class="font-bold text-emerald-800">Benefit:</p>
        <p class="text-emerald-900 font-bold text-sm mt-0.5">${benefit}</p>
      </div>

      <div class="space-y-3 text-xs text-slate-700">
        <p><strong>Application Guide:</strong> ${applySteps}</p>
        <div>
          <p class="font-bold text-slate-800 mb-1">Mandatory Documents Required:</p>
          <ul class="list-disc pl-4 text-slate-600 space-y-1">
            ${docsList.map(doc => `<li>${doc}</li>`).join('')}
          </ul>
        </div>
      </div>

      <div class="mt-5 flex flex-col sm:flex-row gap-2">
        <button onclick="askBotAbout('${title.replace(/'/g, "\\'")}')" class="flex-1 bg-emerald-700 hover:bg-emerald-800 text-white text-xs py-2.5 rounded-xl font-bold transition">
          Ask AI Assistant
        </button>
        <a href="${applyUrl}" target="_blank" rel="noopener noreferrer" class="flex-1 text-center bg-slate-900 hover:bg-slate-800 text-white text-xs py-2.5 rounded-xl font-bold transition flex items-center justify-center gap-1">
          Apply on Official Portal ↗
        </a>
      </div>
    `;
  }
}

function closeModal() {
  const modal = document.getElementById('schemeModal');
  if (modal) modal.classList.add('hidden');
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

  if (audioUrl) {
    const audioEl = document.createElement('audio');
    audioEl.className = 'w-full mt-2 h-8';
    audioEl.controls = true;
    audioEl.src = audioUrl;
    div.appendChild(audioEl);
    audioEl.play().catch(() => {});
  }

  wrapper.appendChild(div);
  chatEl.appendChild(wrapper);
  chatEl.scrollTop = chatEl.scrollHeight;
  return wrapper;
}

// ================= FIXED VOICE RECORDING LOGIC =================
let mediaRecorder = null;
let audioChunks = [];
let isRecording = false;

async function toggleRecording() {
  const micBtn = document.getElementById('micBtn');

  if (!isRecording) {
    try {
      const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
      
      let options = {};
      if (MediaRecorder.isTypeSupported('audio/webm')) {
        options = { mimeType: 'audio/webm' };
      } else if (MediaRecorder.isTypeSupported('audio/mp4')) {
        options = { mimeType: 'audio/mp4' };
      }

      mediaRecorder = new MediaRecorder(stream, options);
      audioChunks = [];

      mediaRecorder.ondataavailable = (e) => {
        if (e.data && e.data.size > 0) {
          audioChunks.push(e.data);
        }
      };

      mediaRecorder.onstop = () => {
        const mimeType = mediaRecorder.mimeType || 'audio/webm';
        const audioBlob = new Blob(audioChunks, { type: mimeType });
        
        stream.getTracks().forEach(track => track.stop());

        if (audioBlob.size > 1500) {
          sendVoiceMessage(audioBlob);
        } else {
          addMessage('Recording was too short or silent. Please try speaking again.', 'bot');
        }
      };

      mediaRecorder.start(250);
      isRecording = true;

      if (micBtn) {
        micBtn.classList.add('bg-red-600', 'text-white', 'animate-pulse');
        micBtn.classList.remove('text-emerald-600', 'border-emerald-600');
        micBtn.title = "Click again to STOP and Send";
        micBtn.innerText = "⏹️";
      }
    } catch (err) {
      console.error("Mic Access Error:", err);
      alert('Microphone access denied or not available.');
    }
  } else {
    if (mediaRecorder && mediaRecorder.state !== 'inactive') {
      mediaRecorder.stop();
    }
    isRecording = false;

    if (micBtn) {
      micBtn.classList.remove('bg-red-600', 'text-white', 'animate-pulse');
      micBtn.classList.add('text-emerald-600', 'border-emerald-600');
      micBtn.title = "Voice Input";
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
    const ext = audioBlob.type.includes('mp4') ? 'mp4' : 'webm';
    formData.append('audio', audioBlob, `recording.${ext}`);
    formData.append('session_id', sessionId || '');

    const res = await fetch('/voice-chat', { method: 'POST', body: formData });
    const data = await res.json();
    sessionId = data.session_id;

    if (loadingMsg) loadingMsg.remove();
    
    if (data.transcript && data.transcript.trim() !== '.' && data.transcript.trim().length > 1) {
      addMessage(data.transcript, 'user');
      addMessage(data.reply, 'bot', false, data.audio_url);
    } else {
      addMessage("Sorry, I couldn't hear you clearly. Please try speaking again.", 'bot');
    }

  } catch (err) {
    console.error("Voice Chat API Error:", err);
    if (loadingMsg) loadingMsg.remove();
    addMessage('Voice processing error. Please try typing.', 'bot');
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
    addMessage(data.reply || data.response, 'bot');
  } catch (err) {
    if (loadingMsg) loadingMsg.remove();
    addMessage('AI response error.', 'bot');
  } finally {
    if (sendBtn) sendBtn.disabled = false;
    inputEl.focus();
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

// ================= DYNAMIC BACKEND ELIGIBILITY ENGINE =================

function openEligibilityModal() {
  const modal = document.getElementById('eligibilityModal');
  if (modal) modal.classList.remove('hidden');
}

function closeEligibilityModal() {
  const modal = document.getElementById('eligibilityModal');
  if (modal) modal.classList.add('hidden');
}

function resetEligibilityForm() {
  const formEl = document.getElementById('eligibilityForm');
  const resultsEl = document.getElementById('eligibilityResults');
  if (formEl) formEl.classList.remove('hidden');
  if (resultsEl) resultsEl.classList.add('hidden');
}

async function calculateEligibility(event) {
  if (event) event.preventDefault();

  const ageVal = parseInt(document.getElementById('userAge')?.value) || 0;
  const genderVal = document.getElementById('userGender')?.value || 'female';
  const stateVal = document.getElementById('userState')?.value || 'DL';
  const occupationVal = document.getElementById('userOccupation')?.value || 'student';
  const incomeVal = parseInt(document.getElementById('userIncome')?.value) || 250000;

  const payload = {
    age: ageVal,
    gender: genderVal,
    state: stateVal,
    occupation: occupationVal,
    income: incomeVal
  };

  const formEl = document.getElementById('eligibilityForm');
  const resultsEl = document.getElementById('eligibilityResults');
  const listEl = document.getElementById('matchedSchemesList');
  const countHeader = document.getElementById('resultsCountHeader');

  if (listEl) listEl.innerHTML = `<p class="text-slate-500 text-center py-4">Checking eligibility with backend server...</p>`;
  if (formEl) formEl.classList.add('hidden');
  if (resultsEl) resultsEl.classList.remove('hidden');

  try {
    const res = await fetch('/api/check-eligibility', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(payload)
    });

    const data = await res.json();
    const matchedSchemes = data.matched_schemes || [];

    if (countHeader) countHeader.innerText = `Matched (${matchedSchemes.length}) Eligible Schemes`;

    if (!listEl) return;
    listEl.innerHTML = '';

    if (matchedSchemes.length === 0) {
      listEl.innerHTML = `<p class="text-slate-400 text-center py-4">No specific schemes matched your criteria. Try adjusting details.</p>`;
      return;
    }

    matchedSchemes.forEach((scheme) => {
      const schemeTitle = scheme.name || scheme.title || "Government Scheme";
      const schemeCategory = scheme.category || "General";
      const schemeBenefit = scheme.benefits || scheme.benefit || "Financial / Welfare Benefit";

      const item = document.createElement('div');
      item.className = "p-3 bg-slate-50 border border-slate-200 rounded-xl flex justify-between items-center hover:bg-emerald-50/50 transition cursor-pointer mb-2";
      item.onclick = () => {
        closeEligibilityModal();
        openModal(scheme.id);
      };
      item.innerHTML = `
        <div>
          <span class="text-[9px] font-bold uppercase text-emerald-800 bg-emerald-100 px-2 py-0.5 rounded">${schemeCategory}</span>
          <h5 class="font-bold text-slate-800 text-xs mt-1">${schemeTitle}</h5>
          <p class="text-[11px] text-emerald-700 font-semibold">${schemeBenefit}</p>
        </div>
        <span class="text-xs text-blue-600 font-bold">View →</span>
      `;
      listEl.appendChild(item);
    });

  } catch (err) {
    console.error("Eligibility API Error:", err);
    if (listEl) listEl.innerHTML = `<p class="text-red-500 text-center py-4">Error connecting to server. Please try again.</p>`;
  }
}

// APP INITIALIZATION
fetchSchemesFromBackend();

if (chatEl && chatEl.children.length === 0) {
  addMessage("Hello! 🙏 I am your JanSeva AI Assistant. Ask me about any central or state scheme.", 'bot');
}
setQuickReplies(DEFAULT_QUICK_REPLIES);