const text = `<br><img src='data:image/png;base64,iVBORw0KGgo=' class='quiz-image' style='max-width: 100%; height: auto;' /><br>`;
const imgRegex = /<img[^>]+src=['"][^'"]+['"][^>]*\/?>/gi;
console.log(text.replace(imgRegex, '[IMG]'));
