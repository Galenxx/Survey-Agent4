const testInput = `| 项目 | 内容 |
|------|------|
| **研究主题** | Large Language Model |`;

function preprocessMarkdown(text) {
  return text.replace(/^\|[\s\S]*?\|$/gm, (line) => {
    const cells = line.split('|').filter((_, i, arr) => i > 0 && i < arr.length - 1);
    if (cells.every(c => c.trim() === '' || /[-: ]+/.test(c.trim()))) {
      return '|' + cells.map(() => '---').join('|') + '|';
    }
    return line;
  });
}

const result = preprocessMarkdown(testInput);
console.log('Input:');
console.log(testInput);
console.log('\nOutput:');
console.log(result);
console.log('\nExpected separator row: |---|---|---|');
