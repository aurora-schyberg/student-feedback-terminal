function editText(name) {
  var elem = document.getElementsByName(name);
  console.info(elem);
  elem[0].disabled = !elem[0].disabled;
  console.info(elem.disabled);
}

function sendText(name) {
  var elem = document.getElementsByName(name);

  if (!elem[0].disabled) {
    return;
  }

  if (!window.confirm("Do you really want to send this text?")) {
    return;
  }

  console.info("Woof");

  var req = new XMLHttpRequest();
  var url = "send_message";
  var params = "radius_user=a&radius_pass=b&rc_user=c&rc_pass=d"

  req.open("POST", url)

  req.onreadystatechange = function () {
    if (req.readyState == 4 && req.status == 200) {
      alert(req.responseText);
    }
  }

  req.send(params)
}
var _table_ = document.createElement('table'),
  _tr_ = document.createElement('tr'),
  _th_ = document.createElement('th'),
  _td_ = document.createElement('td');


//Deletes Selected Row
function delete_this_row() {
  // event.target will be the input element.
  var td = event.target.parentNode;
  var tr = td.parentNode; // the row to be removed
  tr.parentNode.removeChild(tr);
}

function copy_to_clip(id) {
  var text_box = document.getElementById(id);
  text_box.focus();
  text_box.select();
  document.execCommand('copy');
}


// Builds the HTML Table out of myList json data from Ivy restful service.
function buildHtmlTable(arr) {
  var table = _table_.cloneNode(false),
    columns = addAllColumnHeaders(arr, table);

  for (var i = 0, maxi = arr.length; i < maxi; ++i) {
    var tr = _tr_.cloneNode(false);
    for (var j = 0, maxj = columns.length; j < maxj; ++j) {
      var td = _td_.cloneNode(false);
      cellValue = arr[i][columns[j]];
      console.info("%d %d", i, j)
      if (j == 2) {
        var t = document.createElement("textarea");
        t.textContent = cellValue;
        t.className = "editBox";
        t.id = "textbox" + i.toString();

        td.appendChild(t);
        td.innerHTML += "<button onclick=delete_this_row()>Delete</button>";
        td.innerHTML += "<button onclick=copy_to_clip(\"" + t.id + "\")>Copy to Clipboard</button>";
      }
      else {
        td.appendChild(document.createTextNode(arr[i][columns[j]] || ''));
      }
      tr.appendChild(td);
    }
    table.appendChild(tr);
  }
  return table;
}

// Adds a header row to the table and returns the set of columns.
// Need to do union of keys from all records as some records may not contain
// all records
function addAllColumnHeaders(arr, table) {
  var columnSet = [],
    tr = _tr_.cloneNode(false);
  for (var i = 0, l = arr.length; i < l; i++) {
    for (var key in arr[i]) {
      if (arr[i].hasOwnProperty(key) && columnSet.indexOf(key) === -1) {
        columnSet.push(key);
        var th = _th_.cloneNode(false);
        th.appendChild(document.createTextNode(key));
        tr.appendChild(th);
      }
    }
  }
  table.appendChild(tr);
  return columnSet;
}


function loadTable() {
  var loadData = function (url, callback) {
    var xhr = new XMLHttpRequest();
    xhr.open('GET', url, true);
    xhr.timeout = 100000000;
    xhr.responseType = 'json';
    xhr.onload = function () {
      var status = xhr.status;
      if (status === 200) {
        callback(null, xhr.response);
      } else {
        callback(status, xhr.response);
      }
    };
    xhr.send();
  }

  var usr = document.getElementById("radiuslogin").value;
  var pwd = document.getElementById("current-password").value;
  var post_params = "?user=" + usr + "&passwd=" + pwd

  document.getElementById("data-table").innerHTML = "<th>Loading&nbsp;<img src=\"loading.gif\"></th>"
  var proto = location.protocol;

  console.info(proto + "//" + window.location.hostname + "/scrape_radius")
  loadData(proto + "//" + window.location.hostname + "/scrape_radius" + post_params,
    function (err, dt) {
      var err_text = "";
      console.info(dt)

      if (err == 401) {
        err_text = "Failed to authorize user";
      } else {
        if (dt === null) {
          err_text = "Failed to load"
        } else if (dt.length === 0) {
          err_text = "No students available to load"
        } else {
          try {
            var tdata = buildHtmlTable(dt);
            tdata.id = "data-table";
            document.getElementById("data-table").replaceWith(tdata);
          }
          catch (e) {
            err_text = "Failed to load";
          }
        }
      }

      if (err_text.length > 1) {
        var table = document.getElementById("data-table");
        if (table == null) {
          table = document.createElement("table");
          table.id = "data-table";
        }
        table.innerHTML = "<th>" + err_text + "</th>"; //+ "&nbsp;<button id=\"refresh-button\" onclick=\"loadTable()\">Load Student Info</button></th>"
      }

    });
}

//window.onload = loadTable;
//const interval = setInterval(loadTable, 5000);