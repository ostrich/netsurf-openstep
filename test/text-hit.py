#!/usr/bin/env python3
"""Compile the real nearest-text routines with small layout geometry fixtures.

This isolates geometry from libcss/font loading; it does not replace a full
browser test. No copy of the search algorithm is maintained in this test.
"""
from pathlib import Path
import subprocess
import tempfile

ROOT = Path(__file__).resolve().parents[1]
source = (ROOT / 'content/handlers/html/box_inspect.c').read_text()

def function(name):
    start = source.index(name + '(')
    brace = source.index('{', start)
    depth = 1
    end = brace + 1
    while depth:
        depth += (source[end] == '{') - (source[end] == '}')
        end += 1
    return source[start:end]

code = '''#include <stdbool.h>
#include <stddef.h>
#include <limits.h>
#include <assert.h>
enum { LEFT, TOP, RIGHT, BOTTOM };
enum { BOX_BLOCK, BOX_INLINE_CONTAINER, BOX_TEXT, BOX_FLOAT_LEFT, BOX_FLOAT_RIGHT };
struct box {
 int type, x, y, width, height, padding[4], margin[4];
 struct box *children, *next, *parent, *list_marker, *float_children;
 void *scroll_x, *scroll_y, *object;
 const char *text;
};
struct html_content { struct box *layout; };
static int scrollbar_get_offset(void *bar) { (void)bar; return 0; }
'''
for name, signature in [('box_nearer_text_box', 'static bool '),
                         ('box_nearest_text_box', 'static bool '),
                         ('box_pick_text_box', 'struct box *')]:
    code += signature + function(name) + '\n'
code += '''
int main(void) {
 struct box root = {0}, line = {0}, text = {0}, second = {0}, word = {0};
 struct box marker = {0}, floating = {0};
 struct html_content html = { &root };
 int x, y;
 root.children=&line; root.width=700; root.height=500;
 line.parent=&root; line.type=BOX_INLINE_CONTAINER;
 line.x=20; line.y=300; line.width=200; line.height=24; line.children=&text;
 text.parent=&line; text.type=BOX_TEXT; text.width=200; text.height=24; text.text="selection";
 assert(box_pick_text_box(&html, 40,310,-1,&x,&y)==&text && x==20 && y==10);
 /* One pointer movement can cross the entire line. Clamp to its end. */
 assert(box_pick_text_box(&html, 240,310,-1,&x,&y)==&text && x==200 && y==10);
 assert(box_pick_text_box(&html, 5,310,1,&x,&y)==&text && x==0);
 /* In whitespace between lines, respect the direction of selection. */
 line.next=&second; second.parent=&root; second.type=BOX_INLINE_CONTAINER;
 second.x=20; second.y=350; second.width=200; second.height=24; second.children=&word;
 word.parent=&second; word.type=BOX_TEXT; word.width=200; word.height=24; word.text="next line";
 assert(box_pick_text_box(&html, 70,340,-1,&x,&y)==&text);
 assert(box_pick_text_box(&html, 70,340,1,&x,&y)==&word);
 marker.parent=&line; marker.x=-15; marker.width=10; marker.height=24;
 marker.text="*"; line.list_marker=&marker;
 assert(box_pick_text_box(&html, 7,310,-1,&x,&y)==&marker);
 line.list_marker=NULL; line.next=NULL;
 floating.type=BOX_FLOAT_LEFT; floating.parent=&root; floating.x=50; floating.y=20;
 floating.children=&line; root.children=&floating;
 line.parent=&floating; line.x=10; line.y=5;
 assert(box_pick_text_box(&html, 300,30,-1,&x,&y)==&text && x==200);
 root.children=NULL; x=y=99;
 assert(box_pick_text_box(&html, 70,340,1,&x,&y)==NULL && x==0 && y==0);
 return 0;
}
'''
with tempfile.TemporaryDirectory(prefix='netsurf-text-hit-') as directory:
    path = Path(directory)
    (path / 'test.c').write_text(code)
    subprocess.run(['cc', '-std=c99', '-O2', '-Wall', '-Wextra', '-Werror',
                    str(path / 'test.c'), '-o', str(path / 'test')], check=True)
    subprocess.run([str(path / 'test')], check=True)
print('Nearest-text geometry checks passed')
