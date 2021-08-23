using System.Collections;
using System.Collections.Generic;
using UnityEngine;

public class Drinkable : MonoBehaviour
{
    public enum Liquid
    {
        Coffee,
        Water,
        Beer
    }

    public Liquid liquid;
    public int amount;
}
