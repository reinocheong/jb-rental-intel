// ============================================================
// JB Rentals Auth — Google Apps Script Web App
// 部署为 Web App（Execute as me, Anyone）
// ============================================================

var INTERNAL_SHEET_ID = '1gCynpcBHYgoGiRkfVOJOCOjtiOIl0NuGgpyEexAF3W4';
var RENTALS_SHEET_ID = '1QgWjlUEvFf9auZzptbYI2EEDAeWnKAZcxsXhcCgjJYM';
var TOKEN_TTL_HOURS = 24;

// ── 工具函数 ─────────────────────────────────────────────

function sha256(str) {
  var raw = Utilities.computeDigest(Utilities.DigestAlgorithm.SHA_256, str, Utilities.Charset.UTF_8);
  return raw.map(function(b) {
    return ('0' + (b & 0xFF).toString(16)).slice(-2);
  }).join('');
}

function generateToken() {
  var chars = 'ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789';
  var token = '';
  for (var i = 0; i < 48; i++) {
    token += chars.charAt(Math.floor(Math.random() * chars.length));
  }
  return token;
}

function getSheet_(sheetId, tabName) {
  return SpreadsheetApp.openById(sheetId).getSheetByName(tabName);
}

function json_(obj) {
  return ContentService.createTextOutput(JSON.stringify(obj))
    .setMimeType(ContentService.MimeType.JSON);
}

// ── CORS 支持 ─────────────────────────────────────────────

function addCors_(output) {
  // Allow requests from our GitHub Pages domain and local dev
  return output;
}

// ── 登录：doPost ──────────────────────────────────────────

function doPost(e) {
  var output = ContentService.createTextOutput()
    .setMimeType(ContentService.MimeType.JSON);

  try {
    var body = JSON.parse(e.postData.contents);
    var email = (body.email || '').trim().toLowerCase();
    var password = (body.password || '');

    if (!email || !password) {
      return json_({ error: '邮箱和密码不能为空' });
    }

    var userSheet = getSheet_(INTERNAL_SHEET_ID, '授权用户');
    var data = userSheet.getDataRange().getValues();

    for (var i = 1; i < data.length; i++) {
      var row = data[i];
      var rowEmail = (row[0] || '').trim().toLowerCase();
      var storedHash = (row[1] || '').trim();
      var status = (row[4] || '').trim();
      var expiry = row[3] ? new Date(row[3]) : null;

      if (rowEmail !== email) continue;

      // Check status
      if (status !== 'active') {
        return json_({ error: '账号已停用，请联系客服' });
      }

      // Check expiry
      if (expiry && expiry < new Date()) {
        return json_({ error: '账号已过期，请联系续费' });
      }

      // Verify password
      var inputHash = sha256(password);
      if (inputHash !== storedHash) {
        return json_({ error: '密码错误' });
      }

      // Generate token
      var token = generateToken();
      var now = new Date();
      var expires = new Date(now.getTime() + TOKEN_TTL_HOURS * 3600 * 1000);

      // Store session
      var sessionSheet = getSheet_(INTERNAL_SHEET_ID, '登录会话');
      sessionSheet.appendRow([token, email, now.toISOString(), expires.toISOString()]);

      return json_({
        token: token,
        expires: expires.toISOString(),
        name: (row[2] || email).trim()
      });
    }

    return json_({ error: '邮箱未授权，请联系客服开通' });

  } catch (err) {
    return json_({ error: '服务器错误: ' + err.toString() });
  }
}

// ── 数据接口：doGet ────────────────────────────────────────

function doGet(e) {
  var token = (e.parameter.token || '').trim();

  if (!token) {
    return json_({ error: '缺少 token' });
  }

  // Validate token
  var sessionSheet = getSheet_(INTERNAL_SHEET_ID, '登录会话');
  var sessions = sessionSheet.getDataRange().getValues();
  var valid = false;
  var email = '';

  for (var i = 1; i < sessions.length; i++) {
    if (sessions[i][0] === token) {
      var expires = new Date(sessions[i][3]);
      if (expires > new Date()) {
        valid = true;
        email = sessions[i][1];
      }
      break;
    }
  }

  if (!valid) {
    return json_({ error: '登录已过期，请重新登录' });
  }

  // Read JB Rentals data
  try {
    var rentalsSheet = getSheet_(RENTALS_SHEET_ID, 'JB Rentals');
    var rows = rentalsSheet.getDataRange().getValues();
    if (rows.length < 2) {
      return json_({ error: '暂无数据' });
    }

    var headers = rows[0].map(function(h) { return (h || '').toString().trim().toLowerCase(); });

    // Map header names to output keys
    var listings = [];
    var now = new Date();
    var todayStart = new Date(now.getFullYear(), now.getMonth(), now.getDate());
    var todayNew = 0;
    var propCounter = {};

    for (var r = 1; r < rows.length; r++) {
      var row = rows[r];
      var d = {};
      for (var c = 0; c < headers.length; c++) {
        d[headers[c]] = (row[c] || '').toString().trim();
      }

      var phone = d['phone'] || '';
      if (!phone || phone.length < 7) continue;

      // Today counter
      var scraped = d['scraped at'] || '';
      try {
        if (new Date(scraped) >= todayStart) todayNew++;
      } catch(e) {}

      // Property counter
      var prop = d['property name'] || '';
      if (prop) {
        propCounter[prop] = (propCounter[prop] || 0) + 1;
      }

      // Clean rent
      var rent = (d['rent (rm)'] || '').toLowerCase().replace(/rm\s*/i, '').replace('.00', '').trim();
      if (rent && !isNaN(rent.replace(/,/g, ''))) {
        rent = parseInt(rent.replace(/,/g, '')).toLocaleString();
      }

      listings.push({
        agent: d['agent name'] || '',
        property: prop,
        type: d['listing type'] || '',
        property_type: d['property type'] || '',
        rooms: d['rooms'] || '',
        furnishing: d['furnishing'] || '',
        rent: rent,
        phone: phone,
        link: d['link'] || '',
        remark: d['remark'] || '',
        scraped_at: scraped,
        post_text: d['post text'] || ''
      });
    }

    // Sort newest first
    listings.sort(function(a, b) {
      return (b.scraped_at || '').localeCompare(a.scraped_at || '');
    });

    // Top properties
    var topProps = Object.keys(propCounter).sort(function(a, b) {
      return propCounter[b] - propCounter[a];
    }).slice(0, 10);

    return json_({
      updated_at: now.toISOString(),
      total: listings.length,
      today_new: todayNew,
      top_properties: topProps,
      listings: listings
    });

  } catch (err) {
    return json_({ error: '数据读取失败: ' + err.toString() });
  }
}
