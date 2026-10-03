/**
 * Javascript implementation of basic PEM (Privacy Enhanced Mail) algorithms.
 *
 * See: RFC 1421.
 *
 * @author Dave Longley
 *
 * Copyright (c) 2013-2014 Digital Bazaar, Inc.
 *
 * A Forge PEM object has the following fields:
 *
 * type: identifies the type of message (eg: "RSA PRIVATE KEY").
 *
 * procType: identifies the type of processing performed on the message,
 *   it has two subfields: version and type, eg: 4,ENCRYPTED.
 *
 * contentDomain: identifies the type of content in the message, typically
 *   only uses the value: "RFC822".
 *
 * dekInfo: identifies the message encryption algorithm and mode and includes
 *   any parameters for the algorithm, it has two subfields: algorithm and
 *   parameters, eg: DES-CBC,F8143EDE5960C597.
 *
 * headers: contains all other PEM encapsulated headers -- where order is
 *   significant (for pairing data like recipient ID + key info).
 *
 * body: the binary-encoded body.
 */
var forge = require('./forge');
require('./util');

// shortcut for pem API
var pem = module.exports = forge.pem = forge.pem || {};

/**
 * Encodes (serializes) the given PEM object.
 *
 * @param msg the PEM message object to encode.
 * @param options the options to use:
 *          maxline the maximum characters per line for the body, (default: 64).
 *
 * @return the PEM-formatted string.
 */
pem.encode = function(msg, options) {
  options = options || {};
  var rval = '-----BEGIN ' + msg.type + '-----\r\n';

  // encode special headers
  var header;
  if(msg.procType) {
    header = {
      name: 'Proc-Type',
      values: [String(msg.procType.version), msg.procType.type]
    };
    rval += foldHeader(header);
  }
  if(msg.contentDomain) {
    header = {name: 'Content-Domain', values: [msg.contentDomain]};
    rval += foldHeader(header);
  }
  if(msg.dekInfo) {
    header = {name: 'DEK-Info', values: [msg.dekInfo.algorithm]};
    if(msg.dekInfo.parameters) {
      header.values.push(msg.dekInfo.parameters);
    }
    rval += foldHeader(header);
  }

  if(msg.headers) {
    // encode all other headers
    for(var i = 0; i < msg.headers.length; ++i) {
      rval += foldHeader(msg.headers[i]);
    }
  }

  // terminate header
  if(msg.procType) {
    rval += '\r\n';
  }

  // add body
  rval += forge.util.encode64(msg.body, options.maxline || 64) + '\r\n';

  rval += '-----END ' + msg.type + '-----\r\n';
  return rval;
};

/**
 * Decodes (deserializes) all PEM messages found in the given string.
 *
 * @param str the PEM-formatted string to decode.
 *
 * @return the PEM message objects in an array.
 */
pem.decode = function(str) {
  var rval = [];
  var searchFrom = 0;

  while(searchFrom < str.length) {
    var begin = str.indexOf('-----BEGIN ', searchFrom);
    if(begin === -1) {
      break;
    }
    var typeStart = begin + 11;
    var typeEnd = typeStart;
    while(typeEnd < str.length && _isPemTypeChar(str.charCodeAt(typeEnd))) {
      if(str.charCodeAt(typeEnd) === 45 &&
        str.slice(typeEnd, typeEnd + 5) === '-----') {
        break;
      }
      typeEnd++;
    }
    if(typeEnd === typeStart || str.slice(typeEnd, typeEnd + 5) !== '-----') {
      searchFrom = begin + 11;
      continue;
    }

    var cursor = typeEnd + 5;
    if(cursor < str.length && str.charCodeAt(cursor) === 13) {
      cursor++;
    }
    if(cursor < str.length && str.charCodeAt(cursor) === 10) {
      cursor++;
    }

    var type = str.slice(typeStart, typeEnd);
    var endMark = '-----END ' + type + '-----';
    var end = str.indexOf(endMark, cursor);
    if(end === -1) {
      searchFrom = begin + 11;
      continue;
    }

    var middle = str.slice(cursor, end);
    var headerText = '';
    var bodyText = middle;
    var blank = _findBlankLine(middle);
    if(blank) {
      headerText = middle.slice(0, blank.bodyStart);
      bodyText = middle.slice(blank.bodyStart);
    }
    if(!_isPemBody(bodyText)) {
      searchFrom = begin + 11;
      continue;
    }

    // accept "NEW CERTIFICATE REQUEST" as "CERTIFICATE REQUEST"
    // https://datatracker.ietf.org/doc/html/rfc7468#section-7
    if(type === 'NEW CERTIFICATE REQUEST') {
      type = 'CERTIFICATE REQUEST';
    }

    var msg = {
      type: type,
      procType: null,
      contentDomain: null,
      dekInfo: null,
      headers: [],
      body: forge.util.decode64(bodyText)
    };
    rval.push(msg);
    searchFrom = end + endMark.length;

    // no headers
    if(!headerText) {
      continue;
    }

    // parse headers
    var lines = _splitPemLines(headerText);
    var li = 0;
    var parsed = true;
    while(parsed && li < lines.length) {
      // get line, trim any rhs whitespace
      var line = _trimRightWs(lines[li]);

      // RFC2822 unfold any following folded lines
      for(var nl = li + 1; nl < lines.length; ++nl) {
        var next = lines[nl];
        if(!next || !_isPemSpace(next.charCodeAt(0))) {
          break;
        }
        line += next;
        li = nl;
      }

      // parse header
      var headerParts = _parsePemHeader(line);
      parsed = headerParts;
      if(headerParts) {
        var header = {name: headerParts.name, values: []};
        var values = headerParts.value.split(',');
        for(var vi = 0; vi < values.length; ++vi) {
          header.values.push(ltrim(values[vi]));
        }

        // Proc-Type must be the first header
        if(!msg.procType) {
          if(header.name !== 'Proc-Type') {
            throw new Error('Invalid PEM formatted message. The first ' +
              'encapsulated header must be "Proc-Type".');
          } else if(header.values.length !== 2) {
            throw new Error('Invalid PEM formatted message. The "Proc-Type" ' +
              'header must have two subfields.');
          }
          msg.procType = {version: values[0], type: values[1]};
        } else if(!msg.contentDomain && header.name === 'Content-Domain') {
          // special-case Content-Domain
          msg.contentDomain = values[0] || '';
        } else if(!msg.dekInfo && header.name === 'DEK-Info') {
          // special-case DEK-Info
          if(header.values.length === 0) {
            throw new Error('Invalid PEM formatted message. The "DEK-Info" ' +
              'header must have at least one subfield.');
          }
          msg.dekInfo = {algorithm: values[0], parameters: values[1] || null};
        } else {
          msg.headers.push(header);
        }
      }

      ++li;
    }

    if(msg.procType === 'ENCRYPTED' && !msg.dekInfo) {
      throw new Error('Invalid PEM formatted message. The "DEK-Info" ' +
        'header must be present if "Proc-Type" is "ENCRYPTED".');
    }
  }

  if(rval.length === 0) {
    throw new Error('Invalid PEM formatted message.');
  }

  return rval;
};

function foldHeader(header) {
  var rval = header.name + ': ';

  // ensure values with CRLF are folded
  var values = [];
  var insertSpace = function(match, $1) {
    return ' ' + $1;
  };
  for(var i = 0; i < header.values.length; ++i) {
    values.push(header.values[i].replace(/^(\S+\r\n)/, insertSpace));
  }
  rval += values.join(',') + '\r\n';

  // do folding
  var length = 0;
  var candidate = -1;
  for(var i = 0; i < rval.length; ++i, ++length) {
    if(length > 65 && candidate !== -1) {
      var insert = rval[candidate];
      if(insert === ',') {
        ++candidate;
        rval = rval.substr(0, candidate) + '\r\n ' + rval.substr(candidate);
      } else {
        rval = rval.substr(0, candidate) +
          '\r\n' + insert + rval.substr(candidate + 1);
      }
      length = (i - candidate - 1);
      candidate = -1;
      ++i;
    } else if(rval[i] === ' ' || rval[i] === '\t' || rval[i] === ',') {
      candidate = i;
    }
  }

  return rval;
}

function ltrim(str) {
  var start = 0;
  while(start < str.length && _isPemSpace(str.charCodeAt(start))) {
    start++;
  }
  return start === 0 ? str : str.slice(start);
}

function _isPemSpace(code) {
  return code === 9 || code === 10 || code === 11 || code === 12 ||
    code === 13 || code === 32 || code === 160 || code === 0x1680 ||
    (code >= 0x2000 && code <= 0x200a) || code === 0x2028 ||
    code === 0x2029 || code === 0x202f || code === 0x205f ||
    code === 0x3000 || code === 0xfeff;
}

function _isPemTypeChar(code) {
  return (code >= 48 && code <= 57) || (code >= 65 && code <= 90) ||
    code === 45 || code === 32;
}

function _isPemBody(str) {
  if(!str) {
    return false;
  }
  for(var i = 0; i < str.length; ++i) {
    var code = str.charCodeAt(i);
    var digit = code >= 48 && code <= 57;
    var upper = code >= 65 && code <= 90;
    var lower = code >= 97 && code <= 122;
    if(!_isPemSpace(code) && code !== 43 && code !== 47 && code !== 58 &&
      code !== 61 && !digit && !upper && !lower) {
      return false;
    }
  }
  return true;
}

function _findBlankLine(str) {
  for(var i = 0; i < str.length; ++i) {
    var code = str.charCodeAt(i);
    if(code !== 10 && code !== 13) {
      continue;
    }
    var j = i;
    if(str.charCodeAt(j) === 13) {
      j++;
    }
    if(j < str.length && str.charCodeAt(j) === 10) {
      j++;
    }
    if(j < str.length && (str.charCodeAt(j) === 10 || str.charCodeAt(j) === 13)) {
      if(str.charCodeAt(j) === 13) {
        j++;
      }
      if(j < str.length && str.charCodeAt(j) === 10) {
        j++;
      }
      return {bodyStart: j};
    }
  }
  return null;
}

function _splitPemLines(str) {
  var lines = [];
  var start = 0;
  for(var i = 0; i < str.length; ++i) {
    var code = str.charCodeAt(i);
    if(code !== 10 && code !== 13) {
      continue;
    }
    var end = i;
    if(code === 10 && end > start && str.charCodeAt(end - 1) === 13) {
      end--;
    }
    lines.push(str.slice(start, end));
    if(code === 13 && i + 1 < str.length && str.charCodeAt(i + 1) === 10) {
      i++;
    }
    start = i + 1;
  }
  if(start < str.length || str.length === 0) {
    lines.push(str.slice(start));
  } else {
    lines.push('');
  }
  return lines;
}

function _trimRightWs(str) {
  var end = str.length;
  while(end > 0 && _isPemSpace(str.charCodeAt(end - 1))) {
    end--;
  }
  return end === str.length ? str : str.slice(0, end);
}

function _parsePemHeader(line) {
  var colon = -1;
  for(var i = 0; i < line.length; ++i) {
    var code = line.charCodeAt(i);
    if(code === 58) {
      colon = i;
      break;
    }
    if(code < 33 || code > 126) {
      return null;
    }
  }
  if(colon <= 0 || colon + 1 >= line.length) {
    return null;
  }
  var valueStart = colon + 1;
  while(valueStart < line.length && _isPemSpace(line.charCodeAt(valueStart))) {
    valueStart++;
  }
  if(valueStart >= line.length) {
    return null;
  }
  for(var k = valueStart; k < line.length; ++k) {
    var valueCode = line.charCodeAt(k);
    if((valueCode < 33 || valueCode > 126) && !_isPemSpace(valueCode)) {
      return null;
    }
  }
  return {name: line.slice(0, colon), value: line.slice(valueStart)};
}
