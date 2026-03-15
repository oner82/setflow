
function collectChecked(name){
  const boxes = document.querySelectorAll(`input[name='${name}']:checked`);
  return Array.from(boxes).map(b=>b.value);
}
function setHiddenCodes(formId, hiddenId, checkboxName){
  const codes = collectChecked(checkboxName);
  document.getElementById(hiddenId).value = codes.join(",");
  return codes.length > 0;
}
