"""
Test suite for gitstats_oopmetrics module.
Tests the custom AST-like parser for multi-language OOP metrics.
"""

import unittest
import sys
import os

# Add parent directory to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from gitstats_oopmetrics import (
    parse, walk, iter_child_nodes,
    ModuleDef, ClassDef, InterfaceDef, FunctionDef, ImportDef, AttributeDef,
    Tokenizer, TokenType, OOPMetricsAnalyzer
)


class TestPythonParser(unittest.TestCase):
    """Test Python parsing."""
    
    def test_simple_class(self):
        source = '''
class MyClass:
    def __init__(self):
        pass
    
    def method(self, arg1, arg2):
        return arg1 + arg2
'''
        tree = parse(source, '.py')
        self.assertEqual(len(tree.classes), 1)
        self.assertEqual(tree.classes[0].name, 'MyClass')
        self.assertEqual(len(tree.classes[0].methods), 2)
    
    def test_abstract_class(self):
        source = '''
from abc import ABC, abstractmethod

class AbstractBase(ABC):
    @abstractmethod
    def abstract_method(self):
        pass
'''
        tree = parse(source, '.py')
        self.assertEqual(len(tree.classes), 1)
        self.assertTrue(tree.classes[0].is_abstract)
    
    def test_imports(self):
        source = '''
import os
import sys
from collections import defaultdict
from typing import Dict, List
'''
        tree = parse(source, '.py')
        self.assertGreaterEqual(len(tree.imports), 4)
    
    def test_class_with_bases(self):
        source = '''
class Child(Parent, Mixin):
    pass
'''
        tree = parse(source, '.py')
        self.assertEqual(len(tree.classes), 1)
        self.assertIn('Parent', tree.classes[0].bases)
        self.assertIn('Mixin', tree.classes[0].bases)


class TestJavaParser(unittest.TestCase):
    """Test Java parsing."""
    
    def test_simple_class(self):
        source = '''
public class MyClass {
    private String name;
    
    public MyClass() {}
    
    public void doSomething(String arg) {
        System.out.println(arg);
    }
}
'''
        tree = parse(source, '.java')
        self.assertEqual(len(tree.classes), 1)
        self.assertEqual(tree.classes[0].name, 'MyClass')
    
    def test_abstract_class(self):
        source = '''
public abstract class AbstractBase {
    public abstract void abstractMethod();
    
    public void concreteMethod() {}
}
'''
        tree = parse(source, '.java')
        self.assertEqual(len(tree.classes), 1)
        self.assertTrue(tree.classes[0].is_abstract)
    
    def test_interface(self):
        source = '''
public interface MyInterface {
    void method1();
    String method2(int arg);
}
'''
        tree = parse(source, '.java')
        self.assertEqual(len(tree.interfaces), 1)
        self.assertEqual(tree.interfaces[0].name, 'MyInterface')
    
    def test_imports(self):
        source = '''
import java.util.List;
import java.util.Map;
import com.example.*;

public class Test {}
'''
        tree = parse(source, '.java')
        self.assertEqual(len(tree.imports), 3)


class TestTypeScriptParser(unittest.TestCase):
    """Test TypeScript parsing."""
    
    def test_class(self):
        source = '''
export class MyClass extends BaseClass implements IMyInterface {
    private name: string;
    
    constructor() {
        super();
    }
    
    public doSomething(): void {
        console.log("hello");
    }
}
'''
        tree = parse(source, '.ts')
        self.assertEqual(len(tree.classes), 1)
        self.assertEqual(tree.classes[0].name, 'MyClass')
    
    def test_interface(self):
        source = '''
interface IMyInterface {
    method1(): void;
    method2(arg: string): number;
}
'''
        tree = parse(source, '.ts')
        self.assertEqual(len(tree.interfaces), 1)
        self.assertEqual(tree.interfaces[0].name, 'IMyInterface')
    
    def test_abstract_class(self):
        source = '''
abstract class AbstractHandler {
    abstract handle(): void;
    
    protected log(): void {
        console.log("logged");
    }
}
'''
        tree = parse(source, '.ts')
        self.assertEqual(len(tree.classes), 1)
        self.assertTrue(tree.classes[0].is_abstract)


class TestGoParser(unittest.TestCase):
    """Test Go parsing."""
    
    def test_struct(self):
        source = '''
package main

type MyStruct struct {
    Name string
    Age  int
}

func (m *MyStruct) Method() {
    fmt.Println(m.Name)
}
'''
        tree = parse(source, '.go')
        self.assertEqual(len(tree.classes), 1)
        self.assertEqual(tree.classes[0].name, 'MyStruct')
    
    def test_interface(self):
        source = '''
package main

type Reader interface {
    Read(p []byte) (n int, err error)
}
'''
        tree = parse(source, '.go')
        self.assertEqual(len(tree.interfaces), 1)
        self.assertEqual(tree.interfaces[0].name, 'Reader')


class TestRustParser(unittest.TestCase):
    """Test Rust parsing."""
    
    def test_struct(self):
        source = '''
struct MyStruct {
    name: String,
    age: u32,
}

impl MyStruct {
    fn new(name: String) -> Self {
        MyStruct { name, age: 0 }
    }
    
    fn get_name(&self) -> &str {
        &self.name
    }
}
'''
        tree = parse(source, '.rs')
        self.assertEqual(len(tree.classes), 1)
        self.assertEqual(tree.classes[0].name, 'MyStruct')
    
    def test_trait(self):
        source = '''
trait Drawable {
    fn draw(&self);
    fn bounds(&self) -> Rect;
}
'''
        tree = parse(source, '.rs')
        self.assertEqual(len(tree.interfaces), 1)
        self.assertEqual(tree.interfaces[0].name, 'Drawable')


class TestCppParser(unittest.TestCase):
    """Test C++ parsing."""
    
    def test_class(self):
        source = '''
class MyClass : public BaseClass {
public:
    MyClass();
    void method();
    
private:
    int value;
};
'''
        tree = parse(source, '.cpp')
        self.assertEqual(len(tree.classes), 1)
        self.assertEqual(tree.classes[0].name, 'MyClass')
        self.assertIn('BaseClass', tree.classes[0].bases)
    
    def test_abstract_class(self):
        source = '''
class IDrawable {
public:
    virtual void draw() = 0;
    virtual ~IDrawable() = default;
};
'''
        tree = parse(source, '.cpp')
        self.assertEqual(len(tree.classes), 1)
        self.assertTrue(tree.classes[0].is_abstract)


class TestSwiftParser(unittest.TestCase):
    """Test Swift parsing."""
    
    def test_class(self):
        source = '''
class MyClass: BaseClass {
    var name: String
    let id: Int
    
    func doSomething() {
        print("hello")
    }
}
'''
        tree = parse(source, '.swift')
        self.assertEqual(len(tree.classes), 1)
        self.assertEqual(tree.classes[0].name, 'MyClass')
    
    def test_protocol(self):
        source = '''
protocol Drawable {
    func draw()
    func bounds() -> CGRect
}
'''
        tree = parse(source, '.swift')
        self.assertEqual(len(tree.interfaces), 1)
        self.assertEqual(tree.interfaces[0].name, 'Drawable')


class TestTokenizer(unittest.TestCase):
    """Test the tokenizer."""
    
    def test_string_handling(self):
        source = 'x = "class Foo"'  # Should not detect class in string
        tokenizer = Tokenizer(source, 'python')
        tokens = tokenizer.tokenize()
        # Should have string token, not keyword 'class'
        string_tokens = [t for t in tokens if t.type == TokenType.STRING]
        self.assertEqual(len(string_tokens), 1)
    
    def test_comment_handling(self):
        source = '''
# class Foo:
class Bar:
    pass
'''
        tokenizer = Tokenizer(source, 'python')
        tokens = tokenizer.tokenize()
        # Should have comment token with 'class Foo' in it
        keywords = [t for t in tokens if t.type == TokenType.KEYWORD and t.value == 'class']
        self.assertEqual(len(keywords), 1)  # Only Bar's class


class TestWalkFunctions(unittest.TestCase):
    """Test AST walking utilities."""
    
    def test_walk(self):
        source = '''
class Outer:
    def method1(self):
        pass
    
    def method2(self):
        pass
'''
        tree = parse(source, '.py')
        nodes = list(walk(tree))
        # Should include: ModuleDef, ClassDef, FunctionDef x2
        class_nodes = [n for n in nodes if isinstance(n, ClassDef)]
        func_nodes = [n for n in nodes if isinstance(n, FunctionDef)]
        self.assertEqual(len(class_nodes), 1)
        self.assertEqual(len(func_nodes), 2)
    
    def test_iter_child_nodes(self):
        source = '''
class MyClass:
    def method(self):
        pass
'''
        tree = parse(source, '.py')
        children = list(iter_child_nodes(tree))
        self.assertGreaterEqual(len(children), 1)


if __name__ == '__main__':
    unittest.main()
